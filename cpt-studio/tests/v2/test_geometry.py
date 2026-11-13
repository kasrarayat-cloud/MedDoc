"""contract/geometry.py: where pass 1's citations sit (docs/gemini-migration/FINAL-V2.md 1.2 rules 6-7, 1.5, 3.1 I2, I3 and
G1-G6; step 1c of 8.1). TEXT-ONLY and SYNTHETIC: no network, no provider, no document of the acceptance set.

What is proved here, against the done-when of 8.1 step 1c and 9.3's geometry row:
- I2, words over consecutive units: the exact tier with whitespace runs matching, the fold tier, word boundaries
  (``bounded_positions`` equal to v1's ``normalize._bounded_positions``, and ``bind_words`` equal to v1's binding on the
  same slice, both computed in the test over fixtures and random texts), words across units and across a hard wrap, a
  unit edge that cuts a word, and every failure a closed-list reason (BoundedPositionsTests, BindWordsTests);
- I3 and closures: runs consecutive in one paragraph, the 12-unit bound, unknown ids, anchors and their words
  (RunTests, AnchorTests, LayoutTests);
- G2 and containment: starts, order, N0 at the text start, mid-line and mid-unit labels, closers, overlaps; E2's wrap (a
  label and the act in one paragraph, read as the nursing entry), E4 (two labels on one line give two sections), E3 (an
  "as above" restatement lies in the endoscopist's part, the act in the nursing note's), an act after a closer
  (SectionTests, ContainmentTests); an overlap with a section listed LATER, on every section involved, and spans over
  the sections sorted by offset (triage 1c#2); an empty N0 before a section at the first character (DECISIONS D199);
- G1: every link type with a positive and a negative fixture (LinkTests); ``section`` only inside the start's or a
  closing source's place (1c#1); ``antecedent`` units ending before the anchor's first unit (1c#5); a lesion's and a
  person's ``statement`` in its own units, a session's in its examination's closure (1c#3, D207);
- G3's statement tie, G4's inheritance edge, G6's restatements (TargetTests, InheritTests, RestatementTests); the lesion
  tie in the anchor's or a valid restatement's units, never their closure (1c#3);
- G5 on GI Note #8's examination told in three sections (accepted) and on D36's W1S-399 reach from a biopsy sentence
  (extent_inferred), and its other arms (ExtentTests); D198: a reach from another act's valid restatement is inferred,
  one from a denial's anchor is not. Both documents are development documents of FRESH-1, embedded byte for byte, each
  sha256 asserted; neither they nor any synthetic fixture here hashes, as written or stripped, to any line of the
  acceptance set's DEV-EXCLUSION.sha256, asserted in FixtureTests;
- every failure makes the fact UNRESOLVED with a closed-list reason and never raises (PropertyTests); and 5.7 measure 4
  (SingleCharacterGeometry, NoWordLists) holds over the module, each rule refusing a planted control (GuardTests).
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio.interpretation import lexicon as v1_lexicon
from studio.interpretation import normalize as v1_normalize
from studio.interpretation.contract import geometry, segment
from studio.interpretation.contract.geometry import Anchor, Event, Layout, Restatement, Section, Sections
from studio.interpretation.contract.types import FactState, Link, Reason, RestatementRole, Source, Span, Unit

APP = Path(__file__).resolve().parents[2]
GEOMETRY = APP / 'studio' / 'interpretation' / 'contract' / 'geometry.py'
DEV_EXCLUSION = APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256'
DONE, DENIED = FactState.SUPPORTED, FactState.NEGATED
I_REASONS = {Reason.UNIT_UNKNOWN, Reason.UNITS_NOT_CONSECUTIVE, Reason.SOURCE_TOO_LONG, Reason.WORDS_NOT_IN_UNITS,
             Reason.WORDS_NOT_BOUNDED}
G1_REASONS = {Reason.GEOMETRY_STATEMENT, Reason.GEOMETRY_SECTION, Reason.GEOMETRY_FRAME, Reason.GEOMETRY_PLACING,
              Reason.GEOMETRY_DOCUMENT_FRAME, Reason.GEOMETRY_ANTECEDENT, Reason.GEOMETRY_OTHER_STATEMENT}


def src(units, words: str = '', link: Link = Link.STATEMENT) -> Source:
    return Source(tuple(units), words, link)


def unit_with(layout: Layout, fragment: str) -> str:
    """The id of the one unit holding ``fragment``, found with any whitespace run matching any whitespace run."""
    pattern = r'\s+'.join(re.escape(part) for part in fragment.split())
    found = list(re.finditer(pattern, layout.text))
    assert len(found) == 1, (fragment, len(found))
    hits = [unit for unit in layout.units if unit.start <= found[0].start() and found[0].end() <= unit.end]
    assert len(hits) == 1, fragment
    return hits[0].id


def offset_of(text: str, fragment: str) -> int:
    assert text.count(fragment) == 1, fragment
    return text.index(fragment)


def v1_locate(passage: str, words: str):
    """v1's binding of ``words`` in one passage (normalize.Normalizer._locate_words, its two tiers over one passage),
    computed with v1's own _mapped, _bounded_positions, fold and fold_char: (start, end) in the passage, or None."""
    for tier, needle in (('exact', ' '.join(words.split())), ('normalized', v1_lexicon.fold(words))):
        if not needle:
            continue
        hay, starts, ends = v1_normalize._mapped(passage, v1_lexicon.fold_char if tier == 'normalized' else None)
        positions = v1_normalize._bounded_positions(hay, needle)
        if positions:
            return starts[positions[0]], ends[positions[0] + len(needle) - 1]
    return None


# --- the synthetic report and pass 1's citations of it ----------------------------------------------------------------

DOC = (
    'COLONOSCOPY REPORT\n'
    'Date of service: 11/09/2026\n'
    'Endoscopist: Anselm Wrenfield, MD (fictional)\n'
    'Location: Endoscopy Suite 3\n'
    '\n'
    'History: Prior colonoscopy in 2023 with removal of two adenomas. At that time a clip was placed.\n'
    '\n'
    'Findings: The colonoscope was advanced to the cecum. A 6 mm sessile polyp in the sigmoid colon was removed with a\n'
    'cold snare. Neither biopsy nor tattoo was performed. All of the above was done today by the endoscopy team.\n'
    'Biopsies were taken from the\n'
    'Ascending colon with cold forceps.\n'
    'Endoscopist: see below. Nurse: A 4 mm polyp in the rectum was removed with a cold snare.\n'
    'Documented by Jo Rowe, RN: A 3 mm polyp in the descending colon at approx.\n'
    '30 cm, removed en bloc with a cold snare.\n'
    '\n'
    'Impression: Polypectomy as above; a sigmoid polyp and a 2 mm flat lesion of the transverse colon.\n'
)

# a nursing note closed by its signature, then the endoscopist's narrative resumed (closers, 1.4 SECTION.end)
CLOSED = (
    'PROCEDURE NOTE\n'
    '\n'
    'Findings: The colonoscope was advanced to the cecum.\n'
    'Nursing note: A biopsy of the rectum was taken.\n'
    'Documented by Jo Rowe, RN.\n'
    'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n'
    'Plan: Repeat colonoscopy in 5 years.\n'
)

# a label in the middle of a unit: one sentence, two parts (FINAL-V2 1.2: "A section may start in the middle of a unit")
MIDUNIT = ('Findings: cecum reached; CRNA note: cold snare polypectomy of the sigmoid polyp was performed under '
           'anesthesia care\n')

# E3 (S4's failure class): the act told in the nursing note, the endoscopist's line only pointing back ("as above")
E3_DOC = ('Per nursing note: 6 mm sessile polyp in the sigmoid colon removed with cold snare, retrieved.\n'
          'Endoscopist: Polypectomy as above, no bleeding.\n')

# the examination and a biopsy told in one sentence (D36's #12 shape: the shared sentence is the examination's own)
SHARED = 'The colonoscope was advanced to the cecum and a biopsy of the cecum was taken.\nThe prep was good.\n'

# an unpunctuated bulleted list: one paragraph whose units are one sentence closure (arbiter triage 1c#3's input)
FINDINGS = ('FINDINGS\n'
            '- 6 mm sessile polyp in the sigmoid colon, removed with a cold snare\n'
            '- 4 mm polyp in the rectum, left in place\n'
            '- Diverticulosis of the descending colon\n')

# a biopsy restated in the impression (arbiter triage 1c#4's input: D36's hazard reached through a restatement)
IMPRESSION = ('COLONOSCOPY\n'
              'The colonoscope was inserted and advanced under direct vision.\n'
              'Biopsies of the ascending colon were taken for microscopic colitis.\n'
              '\n'
              'IMPRESSION\n'
              'Ascending colon biopsies for microscopic colitis.\n')

# a reach told in the sentence of a denial (D198: a denial's anchor is no act's)
INTUBATION = 'The colonoscope was advanced.\nThe terminal ileum was intubated and no biopsies were taken.\n'

# an act restated in an impression written as an unpunctuated list (a restatement's closure is not its unit, 1c#3)
LISTED = ('Findings: A sigmoid polyp was removed with a cold snare.\n'
          '\n'
          'IMPRESSION\n'
          '- Sigmoid polyp, removed\n'
          '- Rectal polyp, left in place\n')


class Doc:
    """DOC cut into units, its sections as pass 1 would file them, and its events' anchors."""

    def __init__(self) -> None:
        self.layout = layout = Layout.of(DOC)
        self.title = unit_with(layout, 'COLONOSCOPY REPORT')
        self.date = unit_with(layout, 'Date of service')
        self.author = unit_with(layout, 'Endoscopist: Anselm')
        self.location = unit_with(layout, 'Location: Endoscopy')
        self.history = unit_with(layout, 'History: Prior')
        self.at_that_time = unit_with(layout, 'At that time')
        self.findings = unit_with(layout, 'Findings: The colonoscope')
        self.snare = unit_with(layout, 'A 6 mm sessile polyp')
        self.denial = unit_with(layout, 'Neither biopsy')
        self.frame = unit_with(layout, 'All of the above')
        self.wrap1 = unit_with(layout, 'Biopsies were taken')
        self.wrap2 = unit_with(layout, 'Ascending colon with')
        self.see_below = unit_with(layout, 'see below')
        self.nurse = unit_with(layout, 'Nurse: A 4 mm')
        self.signed = unit_with(layout, 'Documented by Jo Rowe')
        self.signed2 = unit_with(layout, '30 cm, removed')
        self.impression = unit_with(layout, 'Impression:')
        self.section_list = (
            Section('N0', src((), '', Link.SECTION), ()),
            Section('N1', src((self.history,), 'History:', Link.SECTION), ()),
            Section('N2', src((self.findings,), 'Findings:', Link.SECTION), ()),
            Section('N3', src((self.see_below,), 'Endoscopist:', Link.SECTION), ()),
            Section('N4', src((self.nurse,), 'Nurse:', Link.SECTION), ()),
            Section('N5', src((self.signed,), 'Documented by Jo Rowe, RN:', Link.SECTION), ()),
            Section('N6', src((self.impression,), 'Impression:', Link.SECTION), ()),
        )
        self.sections = Sections(layout, self.section_list)
        self.exam = Anchor((self.findings,), 'colonoscope', 'was advanced')
        self.snare_act = Anchor((self.snare,), 'cold snare', 'was removed')
        self.biopsy_denial = Anchor((self.denial,), 'biopsy', 'Neither biopsy nor tattoo was performed')
        self.tattoo_denial = Anchor((self.denial,), 'tattoo', 'nor tattoo was performed')
        self.wrapped_biopsy = Anchor((self.wrap1,), 'Biopsies', 'were taken')
        self.nurse_snare = Anchor((self.nurse,), 'cold snare', 'was removed')
        self.signed_snare = Anchor((self.signed, self.signed2), 'cold snare', 'removed en bloc')
        self.history_removal = Anchor((self.history,), 'removal', 'removal of two adenomas')
        self.history_clip = Anchor((self.at_that_time,), 'clip', 'a clip was placed')
        self.anchors = (self.exam, self.snare_act, self.biopsy_denial, self.tattoo_denial, self.wrapped_biopsy,
                        self.nurse_snare, self.signed_snare, self.history_removal, self.history_clip)
        self.anchored = geometry.anchored_units(self.anchors)
        # the events as G5 reads them (D198): "Neither biopsy nor tattoo was performed" is two denials
        self.events = tuple(Event(anchor, (), DENIED if anchor in (self.biopsy_denial, self.tattoo_denial) else DONE)
                            for anchor in self.anchors)
        # the sources of the encounter's facts and of the session's kind (G1 document_frame)
        self.frame_units = geometry.frame_units((src((self.date,), '11/09/2026', Link.DOCUMENT_FRAME),
                                                 src((self.author,), 'Anselm Wrenfield, MD', Link.DOCUMENT_FRAME),
                                                 src((self.title,), 'COLONOSCOPY', Link.DOCUMENT_FRAME)))

    def start(self, unit_id: str) -> int:
        unit = self.layout.unit(unit_id)
        assert unit is not None
        return unit.start

    def subject(self, anchor: Anchor) -> geometry.Subject:
        return geometry.event_subject(self.layout, self.sections, anchor)

    def links(self, subject: geometry.Subject, source: Source) -> tuple:
        return geometry.link_reasons(self.layout, self.sections, subject, source, self.frame_units)

    def extent(self, examination=0) -> geometry.Extent:
        """G5's units for the session whose examination is the event at ``examination`` (the colonoscope's, by
        default)."""
        return geometry.extent_units(self.layout, self.sections, self.events, examination)


class FixtureTests(SimpleTestCase):
    def test_the_development_documents_are_embedded_byte_for_byte(self):
        self.assertEqual(hashlib.sha256(NOTE8.encode('utf-8')).hexdigest(), NOTE8_SHA256)
        self.assertEqual(hashlib.sha256(W1S399.encode('utf-8')).hexdigest(), W1S399_SHA256)
        self.assertEqual(len(NOTE8), 19398)

    def test_no_document_here_is_on_the_acceptance_exclusion_list(self):
        # FINAL-V2 9.6: development documents only; the list holds hashes alone, as written and stripped
        with open(DEV_EXCLUSION, encoding='ascii') as handle:
            excluded = {line.strip() for line in handle if line.strip()}
        self.assertTrue(excluded and all(len(value) == 64 for value in excluded), 'the exclusion list is readable')
        documents = {'NOTE8': NOTE8, 'W1S399': W1S399, 'DOC': DOC, 'CLOSED': CLOSED, 'MIDUNIT': MIDUNIT,
                     'E3_DOC': E3_DOC, 'SHARED': SHARED, 'FINDINGS': FINDINGS, 'IMPRESSION': IMPRESSION,
                     'INTUBATION': INTUBATION, 'LISTED': LISTED}
        listed = [name for name, text in documents.items()
                  if {hashlib.sha256(text.encode('utf-8')).hexdigest(),
                      hashlib.sha256(text.strip().encode('utf-8')).hexdigest()} & excluded]
        self.assertEqual(listed, [])

    def test_the_synthetic_report_cuts_as_the_fixtures_assume(self):
        doc = Doc()
        self.assertEqual([unit.id for unit in doc.layout.units], [f'S{k}' for k in range(1, 18)])
        self.assertEqual(doc.layout.paragraph(doc.signed), doc.layout.paragraph(doc.signed2))
        self.assertEqual(doc.layout.closure((doc.wrap1,)), (doc.wrap1, doc.wrap2), 'a wrap continued in uppercase')
        self.assertIn('\n', DOC[doc.start(doc.snare):doc.layout.unit(doc.snare).end], 'a joined hard wrap')


# --- I2: words over consecutive units ---------------------------------------------------------------------------------


class BoundedPositionsTests(SimpleTestCase):
    CASES = (('the polyp was removed', 'polyp'), ('polyps were removed', 'polyp'), ('a polyp, polyp', 'polyp'),
             ('aaaa', 'aa'), ('x_y y', 'y'), ('snare-polypectomy', 'snare'), ('cold snare', 'cold snare'),
             ('(rectum)', 'rectum'), ('rectum', 'rect'), ('', 'a'), ('a', 'a'), ('7 mm', 'mm'), ('7mm', 'mm'),
             ('no, no.', 'no'), ('.no.', '.'), ('cafe\u0301', 'cafe'), ('\u00e9t\u00e9', 't'), ('a b', ' '))

    def test_equal_to_v1s_on_fixtures(self):
        for hay, needle in self.CASES:
            with self.subTest(hay=hay, needle=needle):
                self.assertEqual(geometry.bounded_positions(hay, needle), v1_normalize._bounded_positions(hay, needle))

    @hypothesis.settings(max_examples=400, deadline=None, database=None)
    @hypothesis.given(st.text(alphabet=st.sampled_from(list('ab_ -.\u00e9')), max_size=24),
                      st.text(alphabet=st.sampled_from(list('ab_ -.\u00e9')), min_size=1, max_size=4))
    def test_equal_to_v1s_on_random_texts(self, hay, needle):
        self.assertEqual(geometry.bounded_positions(hay, needle), v1_normalize._bounded_positions(hay, needle))

    def test_an_empty_needle_has_no_place(self):
        # v1 is never called with one (both callers skip it) and raises IndexError on a non-empty hay
        self.assertEqual(geometry.bounded_positions('abc', ''), [])
        self.assertEqual(geometry.bounded_positions('', ''), [])


class BindWordsTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def bind(self, units, words, layout=None):
        return geometry.bind_words(layout or self.doc.layout, units, words)

    def test_the_exact_tier_gives_the_revisions_own_slice(self):
        found = self.bind((self.doc.snare,), 'A 6 mm sessile polyp')
        self.assertEqual(found.reasons, ())
        self.assertEqual(found.words.start, self.doc.start(self.doc.snare))
        self.assertEqual(found.words.text, DOC[found.words.start:found.words.end])
        self.assertEqual(found.place, Span(found.words.start, found.words.end))
        self.assertEqual(found.span, Span(self.doc.start(self.doc.snare), self.doc.layout.unit(self.doc.snare).end))

    def test_any_whitespace_run_matches_any_whitespace_run_across_a_joined_hard_wrap(self):
        found = self.bind((self.doc.snare,), 'removed   with a cold snare')
        self.assertEqual(found.reasons, ())
        self.assertEqual(found.words.text, 'removed with a\ncold snare')

    def test_words_may_run_over_consecutive_units(self):
        # 1.2 rule 7 [R:CO-4]: the E2 wrap after "approx." is two units; the words cross them
        found = self.bind((self.doc.signed, self.doc.signed2), 'descending colon at approx. 30 cm')
        self.assertEqual(found.reasons, ())
        self.assertEqual(found.words.text, 'descending colon at approx.\n30 cm')
        crossing = self.bind((self.doc.wrap1, self.doc.wrap2), 'taken from the Ascending colon')
        self.assertEqual(crossing.words.text, 'taken from the\nAscending colon')
        self.assertEqual(self.bind((self.doc.signed,), 'approx. 30 cm').reasons, (Reason.WORDS_NOT_IN_UNITS,),
                         'words outside the cited units are not located, though the next unit holds them')

    def test_the_fold_tier_when_the_exact_tier_fails(self):
        self.assertEqual(self.bind((self.doc.snare,), 'COLD   SNARE').words.text, 'cold snare')
        layout = Layout.of('A cold\u2011snare polypectomy with a \ufb01ne needle and the \u201cclip\u201d.\n')
        for words, expected in (('cold-snare', 'cold\u2011snare'), ('fine needle', '\ufb01ne needle'),
                                ('"clip"', '\u201cclip\u201d'), ('COLD SNARE', 'cold\u2011snare')):
            with self.subTest(words):
                found = geometry.bind_words(layout, ('S1',), words)
                self.assertEqual(found.reasons, ())
                self.assertEqual(found.words.text, expected)

    def test_the_first_occurrence_on_word_boundaries(self):
        # "Polyp" opens "Polypectomy" (no boundary after it); the first bounded occurrence is the later "polyp"
        found = self.bind((self.doc.impression,), 'polyp')
        self.assertEqual(found.words.start, offset_of(DOC, 'sigmoid polyp and') + len('sigmoid '))

    def test_words_not_bounded_and_words_not_in_units(self):
        for words in ('olyp', 'sessile pol', 'mm sessile p'):
            with self.subTest(words):
                self.assertEqual(self.bind((self.doc.snare,), words).reasons, (Reason.WORDS_NOT_BOUNDED,))
        for words in ('hot snare', 'Neither biopsy', '   ', '\n'):
            with self.subTest(words):
                found = self.bind((self.doc.snare,), words)
                self.assertEqual(found.reasons, (Reason.WORDS_NOT_IN_UNITS,))
                self.assertIsNone(found.words)
                self.assertIsNone(found.place)

    def test_a_unit_edge_that_cuts_a_word_is_no_word_boundary(self):
        # a 700-character token is cut at 600 (1.2 rule 4): S2 begins inside the word, so words at its start are not
        # bounded by the revision's own characters, though they would be at the start of the slice alone
        text = 'x' * 700 + ' end.\n'
        layout = Layout.of(text)
        self.assertTrue(layout.units[0].forced and layout.units[1].start == 600)
        self.assertEqual(geometry.bind_words(layout, ('S2',), 'x' * 100).reasons, (Reason.WORDS_NOT_BOUNDED,))
        self.assertIsNotNone(v1_locate(text[600:layout.units[1].end], 'x' * 100), "v1's passage rule would accept it")
        self.assertEqual(geometry.bind_words(layout, ('S1', 'S2'), 'x' * 700).reasons, ())

    def test_empty_words_cite_the_whole_of_the_units(self):
        found = self.bind((self.doc.wrap1, self.doc.wrap2), '')
        self.assertEqual(found.reasons, ())
        self.assertIsNone(found.words)
        self.assertEqual(found.place, found.span)
        self.assertEqual(found.span, Span(self.doc.start(self.doc.wrap1), self.doc.layout.unit(self.doc.wrap2).end))

    def test_a_failed_run_is_reported_and_its_words_are_not_read(self):
        doc = self.doc
        for units, reasons in (((doc.snare, doc.frame), (Reason.UNITS_NOT_CONSECUTIVE,)),
                               ((doc.frame, doc.denial), (Reason.UNITS_NOT_CONSECUTIVE,)),
                               ((doc.snare, doc.snare), (Reason.UNITS_NOT_CONSECUTIVE,)),
                               ((doc.location, doc.history), (Reason.UNITS_NOT_CONSECUTIVE,)),
                               (('S99',), (Reason.UNIT_UNKNOWN,)), ((), (Reason.UNITS_NOT_CONSECUTIVE,))):
            with self.subTest(units=units):
                found = self.bind(units, 'polyp')
                self.assertEqual(found.reasons, reasons)
                self.assertIsNone(found.span)
                self.assertIsNone(found.place)

    @hypothesis.settings(max_examples=300, deadline=None, database=None)
    @hypothesis.given(st.data())
    def test_equal_to_v1s_binding_on_the_same_slice(self, data):
        # v1 bound words in one passage; here the passage is the cited units' slice. Below 600 characters and with one
        # page, a unit's edges never touch a word character, so the two must agree exactly.
        alphabet = list('abAB .,:-\n') + ['\u2011', '\u2019', '\u00ad', '\ufb01', '\u00a0']
        text = data.draw(st.text(alphabet=st.sampled_from(alphabet), min_size=1, max_size=160))
        layout = Layout.of(text)
        hypothesis.assume(layout.units)
        first = data.draw(st.integers(0, len(layout.units) - 1))
        run = [layout.units[first]]
        while (len(run) < 3 and first + len(run) < len(layout.units)
               and layout.units[first + len(run)].paragraph == run[0].paragraph and data.draw(st.booleans())):
            run.append(layout.units[first + len(run)])
        passage = text[run[0].start:run[-1].end]
        low = data.draw(st.integers(0, len(passage)))
        high = data.draw(st.integers(low, len(passage)))
        words = data.draw(st.one_of(st.just(passage[low:high]),
                                    st.text(alphabet=st.sampled_from(alphabet), min_size=1, max_size=6)))
        hypothesis.assume(words)
        found = geometry.bind_words(layout, tuple(unit.id for unit in run), words)
        expected = v1_locate(passage, words)
        if expected is None:
            self.assertIsNone(found.words)
            self.assertIn(found.reasons, ((Reason.WORDS_NOT_IN_UNITS,), (Reason.WORDS_NOT_BOUNDED,)))
        else:
            self.assertEqual(found.reasons, ())
            self.assertEqual((found.words.start, found.words.end),
                             (run[0].start + expected[0], run[0].start + expected[1]))
            self.assertEqual(found.words.text, text[found.words.start:found.words.end])

    def test_the_exact_tier_collapses_whitespace_as_v1_does(self):
        # v1's needle is ' '.join(words.split()); here it is built one character at a time
        for words in ('  a\u2028b\u00a0 c\t', '\u3000x', 'a\x1cb', '', ' '):
            with self.subTest(words=words):
                self.assertEqual(''.join(geometry._collapsed(words)), ' '.join(words.split()))

    def test_the_mapped_slice_equals_v1s(self):
        text = 'A  cold\u2011snare \u00ad\n\n\ufb01ne  \u201cclip\u201d\u00a0x'
        for folded, fold in ((False, None), (True, v1_lexicon.fold_char)):
            with self.subTest(folded=folded):
                chars, starts, ends = geometry._mapped(text, 0, len(text), folded)
                self.assertEqual((''.join(chars), starts, ends), v1_normalize._mapped(text, fold))


# --- I3: runs, anchors, closures --------------------------------------------------------------------------------------


class RunTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def test_one_or_more_consecutive_units_of_one_paragraph(self):
        layout, doc = self.doc.layout, self.doc
        self.assertEqual(layout.run((doc.snare, doc.denial, doc.frame)), ())
        self.assertTrue(layout.consecutive((doc.snare, doc.denial)))
        self.assertFalse(layout.consecutive((doc.denial, doc.snare)))
        self.assertFalse(layout.consecutive((doc.location, doc.history)), 'two paragraphs')
        self.assertFalse(layout.consecutive(()))
        self.assertFalse(layout.consecutive(('S99',)))

    def test_at_most_twelve_units(self):
        text = ' '.join(f'Sentence number {k}.' for k in range(1, 15)) + '\n'
        layout = Layout.of(text)
        self.assertEqual(len(layout.units), 14)
        self.assertEqual(layout.run(tuple(f'S{k}' for k in range(1, 13))), ())
        self.assertEqual(layout.run(tuple(f'S{k}' for k in range(1, 14))), (Reason.SOURCE_TOO_LONG,))
        self.assertEqual(layout.run(('S1', 'S3') + tuple(f'S{k}' for k in range(4, 15))),
                         (Reason.UNITS_NOT_CONSECUTIVE, Reason.SOURCE_TOO_LONG))
        self.assertEqual(layout.run(('S1', 'S77') + tuple(f'S{k}' for k in range(3, 15))),
                         (Reason.UNIT_UNKNOWN, Reason.SOURCE_TOO_LONG))
        self.assertIsNone(layout.closure(tuple(f'S{k}' for k in range(1, 14))))

    def test_the_closure_is_segments(self):
        doc = self.doc
        self.assertEqual(doc.layout.closure((doc.wrap1,)), segment.closure(DOC, doc.layout.units, (doc.wrap1,)))
        self.assertEqual(doc.layout.closure((doc.snare,)), (doc.snare,))
        self.assertIsNone(doc.layout.closure((doc.snare, doc.frame)))
        self.assertIsNone(doc.layout.closure(('S99',)))

    def test_line_and_paragraph(self):
        doc = self.doc
        self.assertEqual((doc.layout.line(doc.see_below), doc.layout.line(doc.nurse)), (12, 12))
        self.assertEqual(doc.layout.paragraph(doc.history), 2)
        self.assertIsNone(doc.layout.line('S99'))
        self.assertIsNone(doc.layout.paragraph('S99'))


class AnchorTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def test_the_anchor_place_is_the_acts_own_words(self):
        found = geometry.locate_anchor(self.doc.layout, self.doc.snare_act)
        self.assertEqual(found.reasons, ())
        self.assertEqual(found.place, Span(found.status_words.start, found.kind_words.end))
        self.assertEqual(DOC[found.place.start:found.place.end], 'was removed with a\ncold snare')

    def test_anchor_words_lie_inside_the_anchor_units(self):
        doc = self.doc
        for anchor in (Anchor((doc.snare,), 'hot snare', 'was removed'), Anchor((doc.snare,), 'cold snare', 'were'),
                       Anchor((doc.signed,), 'cold snare', 'removed en bloc')):
            with self.subTest(anchor=anchor):
                found = geometry.locate_anchor(doc.layout, anchor)
                self.assertEqual(found.reasons, (Reason.ANCHOR_WORDS,))
                self.assertIsNone(found.place)
        wrapped = geometry.locate_anchor(doc.layout, doc.signed_snare)
        self.assertEqual(wrapped.reasons, (), 'an anchor over two units holds words in either')

    def test_an_anchor_run_fails_as_a_source_run(self):
        doc = self.doc
        self.assertEqual(geometry.locate_anchor(doc.layout, Anchor(('S99',), 'a', 'b')).reasons, (Reason.UNIT_UNKNOWN,))
        self.assertEqual(geometry.locate_anchor(doc.layout, Anchor((doc.snare, doc.frame), 'cold snare', 'was')).reasons,
                         (Reason.UNITS_NOT_CONSECUTIVE,))

    def test_empty_anchor_words_place_the_whole_units(self):
        found = geometry.locate_anchor(self.doc.layout, Anchor((self.doc.snare,), '', ''))
        self.assertEqual(found.place, found.span)


class LayoutTests(SimpleTestCase):
    def test_a_layout_is_a_texts_units(self):
        text = 'One. Two.\n'
        units = segment.units(text)
        self.assertEqual(Layout(text, units).units, Layout.of(text).units)
        for bad in ((Unit('S1', 0, 4, 1, 1, 1, False), Unit('S2', 2, 9, 1, 1, 1, False)),
                    (Unit('S1', 0, 40, 1, 1, 1, False),),
                    (Unit('S1', 0, 4, 1, 1, 1, False), Unit('S1', 5, 9, 1, 1, 1, False)),
                    (Unit('S1', 3, 3, 1, 1, 1, False),)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    Layout(text, bad)
        with self.assertRaises(TypeError):
            Layout(b'One.', ())
        with self.assertRaises(TypeError):
            Layout(text, (('S1', 0, 4),))
        with self.assertRaises(TypeError):
            geometry.bind_words(Layout(text, units), ('S1',), None)


# --- G2 and containment -----------------------------------------------------------------------------------------------


class SectionTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def place(self, section_id, sections=None):
        found = (sections or self.doc.sections).place(section_id)
        self.assertIsNotNone(found)
        return found

    def test_each_start_at_its_words_and_each_span_to_the_next_start(self):
        doc, places = self.doc, self.doc.sections.places
        self.assertTrue(all(place.reasons == () for place in places))
        self.assertEqual(self.place('N0').start, 0)
        self.assertEqual(self.place('N0').span, Span(0, doc.start(doc.history)))
        for before, after in zip(places, places[1:]):
            self.assertEqual(before.span.end, after.start)
        self.assertEqual(places[-1].span.end, len(DOC), 'the last section runs to the end of the text')

    def test_two_labels_on_one_line_give_two_sections(self):
        # E4: 'Endoscopist: see below. Nurse: ...' - the Nurse label opens mid-line, where its words begin
        doc = self.doc
        self.assertEqual(doc.layout.line(doc.see_below), doc.layout.line(doc.nurse))
        self.assertEqual(self.place('N4').start, offset_of(DOC, 'Nurse:'))
        self.assertEqual(self.place('N3').span, Span(offset_of(DOC, 'Endoscopist: see'), offset_of(DOC, 'Nurse:')))

    def test_a_label_in_the_middle_of_a_unit_opens_its_section_where_its_words_begin(self):
        layout = Layout.of(MIDUNIT)
        self.assertEqual(len(layout.units), 1)
        sections = Sections(layout, (Section('N0', src(('S1',), 'Findings:', Link.SECTION), ()),
                                     Section('N1', src(('S1',), 'CRNA note:', Link.SECTION), ())))
        self.assertEqual(self.place('N1', sections).start, offset_of(MIDUNIT, 'CRNA note:'))
        self.assertEqual(self.place('N0', sections).span, Span(0, offset_of(MIDUNIT, 'CRNA note:')))
        self.assertEqual(self.place('N1', sections).span, Span(offset_of(MIDUNIT, 'CRNA note:'), len(MIDUNIT)))

    def test_an_empty_opening_part_orders_before_a_section_at_the_first_character(self):
        # DECISIONS D199: an N0 whose start cites no unit is a part of length zero at offset 0. It does not conflict
        # with a section whose words begin at the text's first character, and it contains no unit; so the first
        # labelled section keeps its span and its acts their inheritance ("Per nursing note: ..."), and a
        # document_frame source has no N0 unit to lie in.
        layout = Layout.of(E3_DOC)
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),
                                     Section('N1', src(('S1',), 'Per nursing note:', Link.SECTION), ()),
                                     Section('N2', src(('S2',), 'Endoscopist:', Link.SECTION), ())))
        self.assertEqual([place.reasons for place in sections.places], [(), (), ()])
        self.assertEqual([place.start for place in sections.places], [0, 0, offset_of(E3_DOC, 'Endoscopist:')])
        self.assertIsNone(self.place('N0', sections).span, 'length zero: it contains no unit')
        self.assertEqual(self.place('N1', sections).span, Span(0, offset_of(E3_DOC, 'Endoscopist:')))
        act = Anchor(('S1',), 'cold snare', 'removed')
        self.assertEqual(geometry.inherit_reasons(sections, act), ())
        self.assertEqual(sections.attached(geometry.locate_anchor(layout, act).place).id, 'N1')
        subject = geometry.event_subject(layout, sections, act)
        self.assertEqual(geometry.link_reasons(layout, sections, subject, src(('S1',), 'Per nursing note:',
                                                                              Link.SECTION)), ())
        self.assertEqual(geometry.link_reasons(layout, sections, subject, src(('S1',), '', Link.DOCUMENT_FRAME),
                                               frozenset({'S1'})), (Reason.GEOMETRY_DOCUMENT_FRAME,))
        shifted = '\n' + E3_DOC
        sections = Sections(Layout.of(shifted), (Section('N0', src((), '', Link.SECTION), ()),
                                                 Section('N1', src(('S1',), 'Per nursing note:', Link.SECTION), ())))
        self.assertEqual([place.reasons for place in sections.places], [(), ()])
        # only the EMPTY opening part orders before everything: an N0 citing the same first words conflicts as before
        worded = Sections(layout, (Section('N0', src(('S1',), 'Per nursing note:', Link.SECTION), ()),
                                   Section('N1', src(('S1',), 'Per nursing note:', Link.SECTION), ())))
        self.assertEqual([place.reasons for place in worded.places], [(Reason.SECTION_ORDER,)] * 2)
        # and an empty N0 whose closing source reaches past that first start overlaps it: it would hold units
        closed = Sections(layout, (Section('N0', src((), '', Link.SECTION), (src(('S1',), 'retrieved', Link.SECTION),)),
                                   Section('N1', src(('S1',), 'Per nursing note:', Link.SECTION), ())))
        self.assertEqual([place.reasons for place in closed.places], [(Reason.SECTION_ORDER,)] * 2)

    def test_the_opening_part_is_at_the_text_start(self):
        doc = self.doc
        for start in (src((), '', Link.SECTION), src((doc.title,), 'COLONOSCOPY REPORT', Link.SECTION),
                      src((doc.title,), '', Link.SECTION)):
            with self.subTest(start=start):
                sections = Sections(doc.layout, (Section('N0', start, ()),) + doc.section_list[1:])
                self.assertEqual((self.place('N0', sections).start, self.place('N0', sections).reasons), (0, ()))
        late = Sections(doc.layout, (Section('N0', src((doc.date,), 'Date of service', Link.SECTION), ()),)
                        + doc.section_list[1:])
        self.assertEqual(self.place('N0', late).reasons, (Reason.SECTION_ORDER,), 'a unit stands before it')
        self.assertIsNone(self.place('N0', late).span)
        worded = Sections(doc.layout, (Section('N0', src((), 'COLONOSCOPY', Link.SECTION), ()),) + doc.section_list[1:])
        self.assertEqual(self.place('N0', worded).reasons, (Reason.SECTION_START_UNLOCATED,), 'words with no unit')

    def test_an_unlocated_start(self):
        doc = self.doc
        for start in (src((), '', Link.SECTION), src((doc.findings,), 'Results:', Link.SECTION),
                      src(('S99',), 'Findings:', Link.SECTION), src((doc.findings, doc.denial), '', Link.SECTION)):
            with self.subTest(start=start):
                given = list(doc.section_list)
                given[2] = Section('N2', start, ())
                sections = Sections(doc.layout, given)
                self.assertEqual(self.place('N2', sections).reasons, (Reason.SECTION_START_UNLOCATED,))
                self.assertIsNone(self.place('N2', sections).span)
                self.assertEqual(self.place('N1', sections).reasons, (), "the section before keeps its own facts")
                self.assertIsNone(self.place('N1', sections).span, 'but its end, the next start, is unknown')

    def test_starts_strictly_increase(self):
        doc = self.doc
        swapped = list(doc.section_list)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        sections = Sections(doc.layout, swapped)
        self.assertEqual(self.place('N1', sections).reasons, (Reason.SECTION_ORDER,))
        self.assertEqual(self.place('N2', sections).reasons, (Reason.SECTION_ORDER,))
        self.assertEqual(self.place('N3', sections).reasons, ())
        self.assertEqual(self.place('N0', sections).reasons, (Reason.SECTION_ORDER,),
                         "N1's start lies inside N0's reach as listed (to N2's start): an overlap (1c#2)")
        early = list(doc.section_list)
        early[3] = Section('N3', src((doc.history,), 'Prior colonoscopy', Link.SECTION), ())
        sections = Sections(doc.layout, early)
        self.assertEqual(self.place('N2', sections).reasons, (Reason.SECTION_ORDER,), 'a start after its successor')
        self.assertEqual(self.place('N3', sections).reasons, (Reason.SECTION_ORDER,))
        self.assertIsNone(self.place('N2', sections).span)
        self.assertEqual(self.place('N1', sections).reasons, (Reason.SECTION_ORDER,),
                         "N3's start lies inside N1's reach, whatever its place in the list (1c#2)")
        self.assertEqual(self.place('N0', sections).reasons, ())
        self.assertEqual(geometry.inherit_reasons(sections, doc.history_clip), (Reason.INHERIT_UNATTACHED,),
                         'the misplaced N3 is the last start before the clip: its section is unknown, never N1')

    def test_an_overlap_with_a_section_listed_later_is_out_of_order_on_every_section_involved(self):
        # triage 1c#2: N3 ("Endoscopist: see below.") listed after N5 starts inside N2's reach as listed (to N4's
        # start). Before the repair N2 passed with the span (220, 530), which holds N3's start, and a frame source in
        # N3's own start unit framed N2's snare.
        doc = self.doc
        by_id = {section.id: section for section in doc.section_list}
        sections = Sections(doc.layout, tuple(by_id[name] for name in ('N0', 'N1', 'N2', 'N4', 'N5', 'N3', 'N6')))
        self.assertEqual({place.id: place.reasons for place in sections.places},
                         {'N0': (), 'N1': (), 'N2': (Reason.SECTION_ORDER,), 'N3': (Reason.SECTION_ORDER,),
                          'N4': (Reason.SECTION_ORDER,), 'N5': (Reason.SECTION_ORDER,), 'N6': ()})
        self.assertIsNone(self.place('N2', sections).span)
        self.assertEqual(self.place('N1', sections).span, Span(doc.start(doc.history), doc.start(doc.findings)))
        self.assertEqual(self.place('N6', sections).span, Span(offset_of(DOC, 'Impression:'), len(DOC)))
        snare = geometry.event_subject(doc.layout, sections, doc.snare_act)
        self.assertIsNone(snare.section)
        self.assertEqual(geometry.link_reasons(doc.layout, sections, snare, src((doc.see_below,), 'see below',
                                                                                Link.FRAME), doc.frame_units),
                         (Reason.GEOMETRY_FRAME,))
        self.assertEqual(geometry.inherit_reasons(sections, doc.snare_act), (Reason.INHERIT_UNATTACHED,))
        self.assertEqual(geometry.inherit_reasons(sections, doc.history_clip), (), "N1's acts keep their section")

    def test_each_span_ends_at_the_next_start_in_the_text(self):
        # triage 1c#2: spans are computed over the sections sorted by start offset, so no span holds another start
        doc = self.doc
        for order in (('N0', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6'), ('N0', 'N1', 'N2', 'N4', 'N5', 'N3', 'N6'),
                      ('N0', 'N2', 'N1', 'N3', 'N4', 'N5', 'N6'), ('N0', 'N6', 'N1', 'N2', 'N3', 'N4', 'N5')):
            with self.subTest(order=order):
                by_id = {section.id: section for section in doc.section_list}
                sections = Sections(doc.layout, tuple(by_id[name] for name in order))
                starts = sorted(place.start for place in sections.places)
                for place in sections.places:
                    if place.span is not None:
                        later = [start for start in starts if start > place.start]
                        self.assertEqual(place.span.end, later[0] if later else len(DOC))
                        self.assertFalse([start for start in starts if place.span.start < start < place.span.end])

    def test_a_repeated_section_id_raises(self):
        with self.assertRaises(ValueError):
            Sections(self.doc.layout, self.doc.section_list + (self.doc.section_list[1],))


class ClosedSectionTests(SimpleTestCase):
    """A nursing note closed by its signature (1.4 SECTION.end), then the endoscopist's narrative."""

    def setUp(self):
        self.layout = layout = Layout.of(CLOSED)
        self.ids = {fragment: unit_with(layout, fragment) for fragment in
                    ('PROCEDURE NOTE', 'Findings:', 'Nursing note:', 'Documented by', 'A 5 mm polyp', 'Plan:')}

    def sections(self, end=None, resumed=False):
        ids = self.ids
        given = [Section('N0', src((), '', Link.SECTION), ()),
                 Section('N1', src((ids['Findings:'],), 'Findings:', Link.SECTION), ()),
                 Section('N2', src((ids['Nursing note:'],), 'Nursing note:', Link.SECTION),
                         (src((ids['Documented by'],), 'Documented by Jo Rowe, RN', Link.SECTION),) if end is None
                         else end)]
        if resumed:
            given.append(Section('N2b', src((ids['A 5 mm polyp'],), 'A 5 mm polyp', Link.SECTION), ()))
        given.append(Section('N3', src((ids['Plan:'],), 'Plan:', Link.SECTION), ()))
        return Sections(self.layout, given)

    def anchor(self, fragment, kind, status):
        return Anchor((self.ids[fragment],), kind, status)

    def test_a_closed_section_runs_to_its_closing_source(self):
        sections = self.sections()
        nursing = sections.place('N2')
        self.assertEqual(nursing.reasons, ())
        self.assertEqual(nursing.span, Span(offset_of(CLOSED, 'Nursing note:'), offset_of(CLOSED, 'RN.') + 2))
        biopsy = self.anchor('Nursing note:', 'biopsy', 'was taken')
        self.assertEqual(geometry.inherit_reasons(sections, biopsy), ())
        self.assertEqual(sections.attached(geometry.locate_anchor(self.layout, biopsy).place).id, 'N2')

    def test_an_act_after_the_closer_is_not_the_closed_sections(self):
        sections = self.sections()
        snare = self.anchor('A 5 mm polyp', 'cold snare', 'was removed')
        place = geometry.locate_anchor(self.layout, snare).place
        self.assertEqual(sections.containing(place).id, 'N1', "1.5: the last section whose closer, if any, is after it")
        self.assertIsNone(sections.attached(place), "N1's span ends where the nursing note starts")
        self.assertEqual(geometry.inherit_reasons(sections, snare), (Reason.INHERIT_UNATTACHED,))
        resumed = self.sections(resumed=True)
        self.assertEqual(resumed.attached(place).id, 'N2b', 'a part that resumes after another entry is a new section')

    def test_a_closer_past_the_next_start_is_an_overlap(self):
        sections = self.sections(end=(src((self.ids['Plan:'],), 'Plan:', Link.SECTION),))
        self.assertEqual(sections.place('N2').reasons, (Reason.SECTION_ORDER,))
        self.assertEqual(sections.place('N3').reasons, (Reason.SECTION_ORDER,))

    def test_a_closer_past_the_start_of_a_section_listed_later_is_an_overlap(self):
        # triage 1c#2: the nursing note closed after the snare sentence, and a part starting at the signature listed
        # after the Plan. Before the repair only the next LISTED start (the Plan's) was compared with the closer, so the
        # nursing note kept a span holding the signature part's start.
        ids = self.ids
        sections = Sections(self.layout, (
            Section('N0', src((), '', Link.SECTION), ()),
            Section('N1', src((ids['Findings:'],), 'Findings:', Link.SECTION), ()),
            Section('N2', src((ids['Nursing note:'],), 'Nursing note:', Link.SECTION),
                    (src((ids['A 5 mm polyp'],), 'removed with a cold snare', Link.SECTION),)),
            Section('N3', src((ids['Plan:'],), 'Plan:', Link.SECTION), ()),
            Section('N4', src((ids['Documented by'],), 'Documented by', Link.SECTION), ())))
        self.assertEqual({place.id: place.reasons for place in sections.places},
                         {'N0': (), 'N1': (), 'N2': (Reason.SECTION_ORDER,), 'N3': (Reason.SECTION_ORDER,),
                          'N4': (Reason.SECTION_ORDER,)})
        self.assertIsNone(sections.place('N2').span)
        biopsy = self.anchor('Nursing note:', 'biopsy', 'was taken')
        self.assertEqual(geometry.inherit_reasons(sections, biopsy), (Reason.INHERIT_UNATTACHED,))

    def test_a_closer_before_its_start(self):
        sections = self.sections(end=(src((self.ids['Findings:'],), 'Findings:', Link.SECTION),))
        self.assertEqual(sections.place('N2').reasons, (Reason.SECTION_ORDER,))

    def test_an_unlocated_closer_leaves_the_span_unknown_and_contains_what_follows(self):
        sections = self.sections(end=(src((self.ids['Documented by'],), 'Signed by', Link.SECTION),))
        nursing = sections.place('N2')
        self.assertEqual(nursing.reasons, (Reason.SECTION_START_UNLOCATED,))
        self.assertIsNone(nursing.span)
        snare = self.anchor('A 5 mm polyp', 'cold snare', 'was removed')
        place = geometry.locate_anchor(self.layout, snare).place
        self.assertEqual(sections.containing(place).id, 'N2', 'its end unknown, it may hold the act (fail-closed)')
        self.assertEqual(geometry.inherit_reasons(sections, snare), (Reason.INHERIT_UNATTACHED,))


class ContainmentTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def containing(self, anchor, sections=None, layout=None):
        place = geometry.locate_anchor(layout or self.doc.layout, anchor).place
        self.assertIsNotNone(place)
        found = (sections or self.doc.sections).attached(place)
        return None if found is None else found.id

    def test_each_act_in_the_part_that_tells_it(self):
        doc = self.doc
        for anchor, section in ((doc.exam, 'N2'), (doc.snare_act, 'N2'), (doc.biopsy_denial, 'N2'),
                                (doc.wrapped_biopsy, 'N2'), (doc.history_removal, 'N1'), (doc.history_clip, 'N1')):
            with self.subTest(anchor=anchor):
                self.assertEqual(self.containing(anchor), section)

    def test_e2_a_label_and_the_wrapped_act_in_one_paragraph_read_as_the_nursing_entry(self):
        self.assertEqual(self.containing(self.doc.signed_snare), 'N5')

    def test_e4_the_act_after_the_second_label_is_the_second_labels(self):
        self.assertEqual(self.containing(self.doc.nurse_snare), 'N4')
        self.assertEqual(self.containing(Anchor((self.doc.see_below,), 'see below', 'see below')), 'N3')

    def test_a_mid_unit_label_takes_the_act_told_after_it(self):
        layout = Layout.of(MIDUNIT)
        sections = Sections(layout, (Section('N1', src(('S1',), 'Findings:', Link.SECTION), ()),
                                     Section('N2', src(('S1',), 'CRNA note:', Link.SECTION), ())))
        snare = Anchor(('S1',), 'cold snare polypectomy', 'was performed')
        reach = Anchor(('S1',), 'cecum', 'reached')
        self.assertEqual(self.containing(snare, sections, layout), 'N2', "by the act's words, not its unit's start")
        self.assertEqual(self.containing(reach, sections, layout), 'N1')

    def test_e3_an_as_above_line_lies_in_the_endoscopists_part_and_the_act_in_the_nursing_note(self):
        # Whether a restatement moves the entry is settle's (1.5: only an established ``restates`` role does, and
        # ``refers_back`` never counts); geometry gives each its own section, and the restatement stays valid.
        layout = Layout.of(E3_DOC)
        sections = Sections(layout, (Section('N1', src(('S1',), 'Per nursing note:', Link.SECTION), ()),
                                     Section('N2', src(('S2',), 'Endoscopist:', Link.SECTION), ())))
        act = Anchor(('S1',), 'cold snare', 'removed')
        self.assertEqual(self.containing(act, sections, layout), 'N1')
        restatement = Restatement(('S2',), RestatementRole.REFERS_BACK)
        self.assertEqual(sections.attached(layout.span(restatement.units)).id, 'N2')
        self.assertTrue(geometry.restatement_valid(layout, sections, restatement, geometry.anchored_units((act,))))

    def test_no_section_contains_a_place_before_every_start(self):
        layout = Layout.of('Header line.\nFindings: biopsy taken.\n')
        sections = Sections(layout, (Section('N1', src(('S2',), 'Findings:', Link.SECTION), ()),))
        self.assertEqual(sections.places[0].reasons, (Reason.SECTION_ORDER,), 'N0 is not at the text start')
        self.assertIsNone(sections.containing(Span(0, 6)))


# --- G1: link geometry ------------------------------------------------------------------------------------------------


class LinkTests(SimpleTestCase):
    """Every link type with a positive and a negative fixture (8.1 step 1c)."""

    def setUp(self):
        self.doc = Doc()

    def check(self, subject, source, reasons, message=None):
        self.assertEqual(self.doc.links(subject, source), reasons, message)

    def test_statement(self):
        doc = self.doc
        snare = doc.subject(doc.snare_act)
        self.check(snare, src((doc.snare,), 'sigmoid colon'), ())
        self.check(snare, src((doc.denial,), 'biopsy'), (Reason.GEOMETRY_STATEMENT,))
        # the sentence closure counts: the anchor S11 wraps on to S12 ("... from the / Ascending colon ...")
        wrapped = doc.subject(doc.wrapped_biopsy)
        self.check(wrapped, src((doc.wrap2,), 'Ascending colon'), ())
        # a session: its examination's statement, the anchor's closure included (D207: the examination is an event)
        session = geometry.session_subject(doc.layout, doc.sections, doc.exam)
        self.check(session, src((doc.findings,), 'cecum'), ())
        self.check(session, src((doc.snare,), 'sigmoid colon'), (Reason.GEOMETRY_STATEMENT,))
        self.check(geometry.session_subject(doc.layout, doc.sections, None), src((doc.findings,), 'cecum'),
                   (Reason.GEOMETRY_STATEMENT,))
        wrapped_session = geometry.session_subject(doc.layout, doc.sections, doc.wrapped_biopsy)
        self.check(wrapped_session, src((doc.wrap2,), 'Ascending colon'), (), "the examination's closure")
        # a lesion or a person: its description or name units, never their closure (triage 1c#3)
        lesion = geometry.described_subject(doc.layout, doc.sections, src((doc.snare,), 'A 6 mm sessile polyp'))
        self.check(lesion, src((doc.snare,), 'sigmoid colon'), ())
        self.check(lesion, src((doc.impression,), 'sigmoid polyp'), (Reason.GEOMETRY_STATEMENT,))
        wrapped_lesion = geometry.described_subject(doc.layout, doc.sections, src((doc.wrap1,), 'Biopsies'))
        self.check(wrapped_lesion, src((doc.wrap2,), 'Ascending colon'), (Reason.GEOMETRY_STATEMENT,),
                   "in the description's closure (S11-S12), not its unit")
        person = geometry.described_subject(doc.layout, doc.sections, src((doc.author,), 'Anselm Wrenfield, MD'))
        self.check(person, src((doc.author,), 'Endoscopist:'), ())
        self.check(person, src((doc.date,), ''), (Reason.GEOMETRY_STATEMENT,),
                   'header lines end in no .!?: - one closure (1.2 rule 6) - but the name is the author line alone')
        self.assertEqual(person.statement, (doc.author,))
        self.check(person, src((doc.history,), ''), (Reason.GEOMETRY_STATEMENT,))
        # an object with no statement of its own (the encounter, an anatomy entry): its units need only exist
        self.check(geometry.unplaced_subject(), src((doc.wrap2,), ''), ())
        self.check(geometry.unplaced_subject(), src(('S0',), ''), (Reason.GEOMETRY_STATEMENT,))
        self.check(geometry.section_subject(doc.sections, 'N1'), src((doc.history,), 'History:'),
                   (Reason.GEOMETRY_STATEMENT,))

    def test_section(self):
        doc = self.doc
        snare = doc.subject(doc.snare_act)
        self.check(snare, src((doc.findings,), 'Findings:', Link.SECTION), ())
        self.check(snare, src((doc.history,), 'History:', Link.SECTION), (Reason.GEOMETRY_SECTION,))
        own = geometry.section_subject(doc.sections, 'N1')
        self.check(own, src((doc.history,), 'History:', Link.SECTION), ())
        self.check(own, src((doc.history,), 'History', Link.SECTION), (), 'inside the start words')
        self.check(own, src((doc.findings,), 'Findings:', Link.SECTION), (Reason.GEOMETRY_SECTION,))
        # triage 1c#1: the start is its words; a framing sentence after the label in the same unit is not the start
        self.check(own, src((doc.history,), 'Prior colonoscopy in 2023', Link.SECTION), (Reason.GEOMETRY_SECTION,))
        self.check(own, src((doc.history,), '', Link.SECTION), (Reason.GEOMETRY_SECTION,), 'the whole start unit')
        # the words before a mid-unit label are not that label's section
        layout = Layout.of(MIDUNIT)
        sections = Sections(layout, (Section('N1', src(('S1',), 'Findings:', Link.SECTION), ()),
                                     Section('N2', src(('S1',), 'CRNA note:', Link.SECTION), ())))
        act = geometry.event_subject(layout, sections, Anchor(('S1',), 'cold snare polypectomy', 'was performed'))
        self.assertEqual(geometry.link_reasons(layout, sections, act, src(('S1',), 'CRNA note:', Link.SECTION)), ())
        self.assertEqual(geometry.link_reasons(layout, sections, act, src(('S1',), 'Findings:', Link.SECTION)),
                         (Reason.GEOMETRY_SECTION,))

    def test_section_is_not_the_next_sections_mid_unit_label(self):
        # arbiter triage 1c#1: the act told in N1 cites N2's label, which stands after N1's start in the
        # same unit. Before the repair only "not before the start" was checked, and it passed.
        layout = Layout.of(MIDUNIT)
        sections = Sections(layout, (Section('N1', src(('S1',), 'Findings:', Link.SECTION), ()),
                                     Section('N2', src(('S1',), 'CRNA note:', Link.SECTION), ())))
        reach = geometry.event_subject(layout, sections, Anchor(('S1',), 'cecum', 'reached'))
        self.assertEqual(reach.section.id, 'N1')
        for words, reasons in (('CRNA note:', (Reason.GEOMETRY_SECTION,)), ('', (Reason.GEOMETRY_SECTION,)),
                               ('Findings:', ()), ('Findings', ())):
            with self.subTest(words=words):
                self.assertEqual(geometry.link_reasons(layout, sections, reach, src(('S1',), words, Link.SECTION)),
                                 reasons)

    def test_section_closer(self):
        layout = Layout.of(CLOSED)
        ids = {fragment: unit_with(layout, fragment) for fragment in ('Findings:', 'Nursing note:', 'Documented by')}
        sections = Sections(layout, (
            Section('N0', src((), '', Link.SECTION), ()),
            Section('N1', src((ids['Findings:'],), 'Findings:', Link.SECTION), ()),
            Section('N2', src((ids['Nursing note:'],), 'Nursing note:', Link.SECTION),
                    (src((ids['Documented by'],), 'Documented by Jo Rowe, RN', Link.SECTION),))))
        act = geometry.event_subject(layout, sections, Anchor((ids['Nursing note:'],), 'biopsy', 'was taken'))
        self.assertEqual(geometry.link_reasons(layout, sections, act, src((ids['Documented by'],), 'Jo Rowe, RN',
                                                                          Link.SECTION)), ())
        exam = geometry.event_subject(layout, sections, Anchor((ids['Findings:'],), 'colonoscope', 'was advanced'))
        self.assertEqual(geometry.link_reasons(layout, sections, exam, src((ids['Documented by'],), 'Jo Rowe, RN',
                                                                           Link.SECTION)), (Reason.GEOMETRY_SECTION,))
        closer = src((ids['Documented by'],), 'Documented by Jo Rowe, RN', Link.SECTION)
        self.assertEqual(sections.place('N2').closers, (geometry.locate(layout, closer).place,))
        self.assertEqual(sections.place('N1').closers, ())

    def test_section_lies_inside_a_closing_source_by_offsets(self):
        # triage 1c#1, the closing-source case: the closer is its words; before the repair any source citing the
        # closer's units passed, whatever its words
        layout = Layout.of(CLOSED)
        ids = {fragment: unit_with(layout, fragment) for fragment in ('Findings:', 'Nursing note:', 'Documented by')}
        sections = Sections(layout, (
            Section('N0', src((), '', Link.SECTION), ()),
            Section('N1', src((ids['Findings:'],), 'Findings:', Link.SECTION), ()),
            Section('N2', src((ids['Nursing note:'],), 'Nursing note:', Link.SECTION),
                    (src((ids['Documented by'],), 'Jo Rowe, RN', Link.SECTION),))))
        act = geometry.event_subject(layout, sections, Anchor((ids['Nursing note:'],), 'biopsy', 'was taken'))
        for words, reasons in (('Jo Rowe, RN', ()), ('Jo Rowe', ()), ('Documented by', (Reason.GEOMETRY_SECTION,)),
                               ('', (Reason.GEOMETRY_SECTION,))):
            with self.subTest(words=words):
                self.assertEqual(geometry.link_reasons(layout, sections, act,
                                                       src((ids['Documented by'],), words, Link.SECTION)), reasons)

    def test_frame(self):
        doc = self.doc
        snare = doc.subject(doc.snare_act)
        self.check(snare, src((doc.frame,), 'done today by the endoscopy team', Link.FRAME), ())
        self.check(snare, src((doc.at_that_time,), 'At that time', Link.FRAME), (Reason.GEOMETRY_FRAME,))
        own = geometry.section_subject(doc.sections, 'N1')
        self.check(own, src((doc.at_that_time,), '', Link.FRAME), ())
        self.check(own, src((doc.frame,), '', Link.FRAME), (Reason.GEOMETRY_FRAME,))

    def test_placing(self):
        # any unit that is not the object's own anchor; which acts it governs is pass 2's [R:CO-2]
        doc = self.doc
        clip = doc.subject(doc.history_clip)
        self.check(clip, src((doc.impression,), 'Polypectomy as above', Link.PLACING), ())
        self.check(clip, src((doc.history,), 'in 2023', Link.PLACING), ())
        self.check(clip, src((doc.at_that_time,), 'At that time', Link.PLACING), (Reason.GEOMETRY_PLACING,))
        own = geometry.section_subject(doc.sections, 'N2')
        self.check(own, src((doc.impression,), '', Link.PLACING), ())
        self.check(own, src((doc.findings,), 'Findings:', Link.PLACING), (Reason.GEOMETRY_PLACING,))

    def test_document_frame(self):
        doc = self.doc
        findings = geometry.section_subject(doc.sections, 'N2')
        self.check(findings, src((doc.date,), '11/09/2026', Link.DOCUMENT_FRAME), ())
        self.check(findings, src((doc.title,), '', Link.DOCUMENT_FRAME), ())
        self.check(findings, src((doc.location,), 'Endoscopy Suite 3', Link.DOCUMENT_FRAME),
                   (Reason.GEOMETRY_DOCUMENT_FRAME,))
        self.check(findings, src((doc.frame,), 'today', Link.DOCUMENT_FRAME), (Reason.GEOMETRY_DOCUMENT_FRAME,))
        self.check(geometry.unplaced_subject(), src((doc.date,), '11/09/2026', Link.DOCUMENT_FRAME), ())

    def test_antecedent(self):
        doc = self.doc
        clip = doc.subject(doc.history_clip)
        self.check(clip, src((doc.history,), 'Prior colonoscopy in 2023', Link.ANTECEDENT), ())
        self.check(clip, src((doc.history,), '', Link.ANTECEDENT), ())
        self.check(clip, src((doc.snare,), 'A 6 mm sessile polyp', Link.ANTECEDENT), (Reason.GEOMETRY_ANTECEDENT,))
        self.check(geometry.unplaced_subject(), src((doc.history,), '', Link.ANTECEDENT),
                   (Reason.GEOMETRY_ANTECEDENT,))

    def test_an_antecedent_ends_before_the_anchors_first_unit(self):
        # arbiter triage 1c#5: the anaphoric frame inside the clip's own anchor S6 ("At that time a clip was
        # placed.") is not its antecedent. Before the repair it was measured against the act's own words and passed.
        doc = self.doc
        clip = doc.subject(doc.history_clip)
        self.check(clip, src((doc.at_that_time,), 'At that time', Link.ANTECEDENT), (Reason.GEOMETRY_ANTECEDENT,))
        self.check(clip, src((doc.at_that_time,), '', Link.ANTECEDENT), (Reason.GEOMETRY_ANTECEDENT,))
        # by units: an earlier sentence of the anchor's own run is inside the anchor, not before it
        signed = doc.subject(doc.signed_snare)
        self.check(signed, src((doc.signed,), 'A 3 mm polyp', Link.ANTECEDENT), (Reason.GEOMETRY_ANTECEDENT,))
        self.check(signed, src((doc.nurse,), 'A 4 mm polyp', Link.ANTECEDENT), ())
        # a section's start: an antecedent ends before its first unit, so the words before a mid-unit label do not
        layout = Layout.of(MIDUNIT)
        sections = Sections(layout, (Section('N1', src(('S1',), 'Findings:', Link.SECTION), ()),
                                     Section('N2', src(('S1',), 'CRNA note:', Link.SECTION), ())))
        self.assertEqual(geometry.link_reasons(layout, sections, geometry.section_subject(sections, 'N2'),
                                               src(('S1',), 'cecum reached', Link.ANTECEDENT)),
                         (Reason.GEOMETRY_ANTECEDENT,))

    def test_other_statement(self):
        doc = self.doc
        snare = doc.subject(doc.snare_act)
        self.check(snare, src((doc.impression,), 'Polypectomy as above', Link.OTHER_STATEMENT), ())
        self.check(snare, src(('S99',), '', Link.OTHER_STATEMENT), (Reason.GEOMETRY_OTHER_STATEMENT,))
        self.check(snare, src((), '', Link.OTHER_STATEMENT), (Reason.GEOMETRY_OTHER_STATEMENT,))

    def test_an_unattached_object_has_no_section_or_frame(self):
        layout = Layout.of(CLOSED)
        ids = {fragment: unit_with(layout, fragment) for fragment in ('Findings:', 'Nursing note:', 'A 5 mm polyp')}
        sections = Sections(layout, (
            Section('N0', src((), '', Link.SECTION), ()),
            Section('N1', src((ids['Findings:'],), 'Findings:', Link.SECTION), ()),
            Section('N2', src((ids['Nursing note:'],), 'Nursing note:', Link.SECTION), (
                src((unit_with(layout, 'Documented by'),), '', Link.SECTION),))))
        after = geometry.event_subject(layout, sections, Anchor((ids['A 5 mm polyp'],), 'cold snare', 'was removed'))
        self.assertIsNone(after.section)
        self.assertEqual(geometry.link_reasons(layout, sections, after, src((ids['Findings:'],), 'Findings:',
                                                                            Link.SECTION)), (Reason.GEOMETRY_SECTION,))
        self.assertEqual(geometry.link_reasons(layout, sections, after, src((ids['Findings:'],), '', Link.FRAME)),
                         (Reason.GEOMETRY_FRAME,))


# --- G3, G4, G6 ---------------------------------------------------------------------------------------------------------


class TargetTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def test_a_target_cited_as_statement_has_its_words_inside_the_anchor_units(self):
        doc = self.doc
        self.assertEqual(geometry.target_reasons(doc.layout, doc.snare_act, src((doc.snare,), 'sigmoid colon')), ())
        # in the anchor's closure (G1 holds) but not in its units: G3 is the stricter tie
        source = src((doc.wrap2,), 'Ascending colon')
        self.assertEqual(doc.links(doc.subject(doc.wrapped_biopsy), source), ())
        self.assertEqual(geometry.target_reasons(doc.layout, doc.wrapped_biopsy, source), (Reason.TARGET_DETACHED,))
        self.assertEqual(geometry.target_reasons(doc.layout, doc.wrapped_biopsy,
                                                 src((doc.wrap1, doc.wrap2), 'Ascending colon')),
                         (Reason.TARGET_DETACHED,), 'a wider citation does not bring the words into the anchor')
        self.assertEqual(geometry.target_reasons(doc.layout, doc.wrapped_biopsy,
                                                 src((doc.wrap2,), 'Ascending colon', Link.OTHER_STATEMENT)), (),
                         'only a statement-linked target is tied by G3')

    def test_the_lesion_lies_in_the_anchor_a_restatement_or_before_the_act(self):
        doc = self.doc

        def lesion(anchor, description, restatements=()):
            return geometry.lesion_reasons(doc.layout, doc.sections, anchor, restatements, description, doc.anchored)

        in_anchor = src((doc.snare,), 'A 6 mm sessile polyp')
        later = src((doc.impression,), 'a 2 mm flat lesion of the transverse colon')
        self.assertEqual(lesion(doc.snare_act, in_anchor), ())
        self.assertEqual(lesion(doc.biopsy_denial, in_anchor), (), 'described before the statement: an antecedent')
        self.assertEqual(lesion(doc.history_clip, in_anchor), (Reason.TARGET_DETACHED,), 'described after the act')
        self.assertEqual(lesion(doc.snare_act, later), (Reason.TARGET_DETACHED,))
        restated = (Restatement((doc.impression,), RestatementRole.SUMMARIZES),)
        self.assertEqual(lesion(doc.snare_act, later, restated), (), 'in a restatement of the act')
        on_an_anchor = (Restatement((doc.nurse,), RestatementRole.SUMMARIZES),)
        self.assertEqual(lesion(doc.snare_act, src((doc.nurse,), 'A 4 mm polyp'), on_an_anchor),
                         (Reason.TARGET_DETACHED,), 'an invalid restatement (G6) ties nothing')
        broken = Anchor((doc.snare, doc.frame), 'cold snare', 'was removed')
        self.assertEqual(lesion(broken, in_anchor), (Reason.TARGET_DETACHED,), 'an anchor failing I3 ties nothing')

    def test_the_lesion_tie_is_the_anchor_unit_never_its_closure(self):
        # arbiter triage 1c#3: an unpunctuated bulleted list is one sentence closure (S1-S4). The snare told
        # in S2 is tied to the rectal polyp of S3 (left in place) only through that closure; before the repair the
        # tie, and L1's statement in S3, both passed.
        layout = Layout.of(FINDINGS)
        self.assertEqual(layout.closure(('S2',)), ('S1', 'S2', 'S3', 'S4'))
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),))
        snare = Anchor(('S2',), 'cold snare', 'removed')
        anchored = geometry.anchored_units((snare,))
        rectal = src(('S3',), '4 mm polyp in the rectum')
        self.assertEqual(geometry.lesion_reasons(layout, sections, snare, (), rectal, anchored),
                         (Reason.TARGET_DETACHED,))
        sigmoid = src(('S2',), '6 mm sessile polyp')
        self.assertEqual(geometry.lesion_reasons(layout, sections, snare, (), sigmoid, anchored), ())
        l1 = geometry.described_subject(layout, sections, sigmoid)
        self.assertEqual(l1.statement, ('S2',))
        for source, reasons in ((src(('S3',), 'rectum'), (Reason.GEOMETRY_STATEMENT,)),
                                (src(('S4',), 'descending colon'), (Reason.GEOMETRY_STATEMENT,)),
                                (src(('S2',), 'sigmoid colon'), ())):
            with self.subTest(source=source):
                self.assertEqual(geometry.link_reasons(layout, sections, l1, source), reasons)
        # a restatement ties its own units, not their closure: the act restated in an impression written as a list
        listed = Layout.of(LISTED)
        self.assertEqual(listed.closure(('S3',)), ('S2', 'S3', 'S4'))
        act = Anchor(('S1',), 'cold snare', 'was removed')
        restated = (Restatement(('S3',), RestatementRole.SUMMARIZES),)
        sections = Sections(listed, (Section('N0', src((), '', Link.SECTION), ()),))
        anchored = geometry.anchored_units((act,))
        self.assertEqual(geometry.lesion_reasons(listed, sections, act, restated, src(('S4',), 'Rectal polyp'),
                                                 anchored), (Reason.TARGET_DETACHED,))
        self.assertEqual(geometry.lesion_reasons(listed, sections, act, restated, src(('S3',), 'Sigmoid polyp'),
                                                 anchored), ())

    def test_a_wrapped_description_is_tied_by_its_unit_not_by_the_anchors_closure(self):
        # the anchor S11 wraps on to S12; a description in S12 lies in the anchor's closure, not in its units
        doc = self.doc
        description = src((doc.wrap2,), 'Ascending colon')
        self.assertEqual(geometry.lesion_reasons(doc.layout, doc.sections, doc.wrapped_biopsy, (), description,
                                                 doc.anchored), (Reason.TARGET_DETACHED,))
        whole = Anchor((doc.wrap1, doc.wrap2), 'Biopsies', 'were taken')
        self.assertEqual(geometry.lesion_reasons(doc.layout, doc.sections, whole, (), description, doc.anchored), ())


class InheritTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def test_attached_when_the_anchor_lies_in_the_sections_span(self):
        doc = self.doc
        for anchor in (doc.snare_act, doc.signed_snare, doc.nurse_snare, doc.history_clip):
            with self.subTest(anchor=anchor):
                self.assertEqual(geometry.inherit_reasons(doc.sections, anchor), ())

    def test_unattached_otherwise(self):
        doc = self.doc
        for anchor in (Anchor(('S99',), 'a', 'b'), Anchor((doc.snare,), 'hot snare', 'was removed'),
                       Anchor((doc.denial, doc.frame, doc.wrap1, doc.wrap2, doc.see_below), 'biopsy', 'Endoscopist')):
            with self.subTest(anchor=anchor):
                self.assertEqual(geometry.inherit_reasons(doc.sections, anchor), (Reason.INHERIT_UNATTACHED,))
        broken = list(doc.section_list)
        broken[3] = Section('N3', src((doc.see_below,), 'Surgeon:', Link.SECTION), ())
        sections = Sections(doc.layout, broken)
        self.assertEqual(geometry.inherit_reasons(sections, doc.snare_act), (Reason.INHERIT_UNATTACHED,),
                         "the next start unlocated, N2's end is unknown")
        self.assertEqual(geometry.inherit_reasons(sections, doc.history_clip), ())


class RestatementTests(SimpleTestCase):
    def setUp(self):
        self.doc = Doc()

    def valid(self, units, role, sections=None):
        doc = self.doc
        return geometry.restatement_valid(doc.layout, sections or doc.sections, Restatement(tuple(units), role),
                                          doc.anchored)

    def test_restatement_units_are_not_anchor_units(self):
        doc = self.doc
        self.assertTrue(self.valid((doc.impression,), RestatementRole.SUMMARIZES))
        self.assertTrue(self.valid((doc.frame,), RestatementRole.RESTATES))
        self.assertFalse(self.valid((doc.snare,), RestatementRole.SUMMARIZES), "the snare's own anchor")
        self.assertFalse(self.valid((doc.nurse,), RestatementRole.RESTATES), "another act's anchor")
        self.assertFalse(self.valid((doc.frame, doc.wrap1), RestatementRole.RESTATES), 'part of it an anchor')

    def test_a_title_restatement_lies_in_n0_or_in_a_section_start(self):
        doc = self.doc
        self.assertTrue(self.valid((doc.title,), RestatementRole.TITLE))
        self.assertTrue(self.valid((doc.see_below,), RestatementRole.TITLE), "N3's start")
        self.assertTrue(self.valid((doc.impression,), RestatementRole.TITLE), "N6's start")
        self.assertFalse(self.valid((doc.frame,), RestatementRole.TITLE))

    def test_an_invalid_run_is_ignored(self):
        doc = self.doc
        self.assertFalse(self.valid(('S99',), RestatementRole.SUMMARIZES))
        self.assertFalse(self.valid((doc.frame, doc.impression), RestatementRole.SUMMARIZES))
        self.assertFalse(self.valid((), RestatementRole.SUMMARIZES))


# --- G5 ---------------------------------------------------------------------------------------------------------------


class ExtentTests(SimpleTestCase):
    def test_note8_an_examination_told_in_three_sections_is_accepted(self):
        # GI Note #8 tells its insertion, its completion and the neo-terminal ileum in three parts; the completion and
        # the neo-terminal-ileum sentences anchor no act, so its extent is accepted (CO-6; there is no section test)
        layout = Layout.of(NOTE8)
        self.assertEqual(len(layout.units), 181)
        heading = {name: unit_with(layout, fragment) for name, fragment in (
            ('consent', 'Preprocedure evaluation and consent'),
            ('technique', 'Procedure technique and chronological findings'),
            ('anastomosis', 'Ileocolonic anastomosis and balloon dilation'),
            ('ileum', 'Neo-terminal ileum and segmental mucosal sampling'))}
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),) + tuple(
            Section(name, src((unit,), '', Link.SECTION), ()) for name, unit in heading.items()))
        insertion = unit_with(layout, 'The colonoscope was introduced through the anus')
        completion = unit_with(layout, 'completion of the examination was confirmed')
        ileum = unit_with(layout, 'The neo-terminal ileum was examined for approximately 15 cm')
        examination = Anchor((insertion,), 'colonoscope', 'was introduced')
        acts = (examination,
                Anchor((unit_with(layout, 'Two cold-forceps mucosal biopsies were taken'),), 'biopsies', 'were taken'),
                Anchor((unit_with(layout, 'The balloon was inflated sequentially'),), 'balloon', 'was inflated'),
                Anchor((unit_with(layout, 'Four targeted cold-forceps biopsies were obtained'),), 'biopsies',
                       'were obtained'))
        extent = geometry.extent_units(layout, sections, tuple(Event(act, (), DONE) for act in acts), 0)
        sources = {'reached anastomosis': src((insertion,), 'right-sided ileocolonic anastomosis'),
                   'reached neo_terminal_ileum': src((ileum,), 'The neo-terminal ileum was examined',
                                                     Link.OTHER_STATEMENT),
                   'completion complete': src((completion,), 'completion of the examination was confirmed',
                                              Link.OTHER_STATEMENT)}
        told_in = set()
        for name, source in sources.items():
            with self.subTest(name):
                self.assertEqual(geometry.locate(layout, source).reasons, ())
                self.assertEqual(geometry.extent_reasons(layout, source, extent), ())
                told_in.add(sections.containing(geometry.locate(layout, source).place).id)
        self.assertEqual(told_in, {'consent', 'technique', 'ileum'}, 'three sections')
        biopsy_sentence = src((unit_with(layout, 'Four targeted cold-forceps biopsies were obtained'),), 'ileal mucosa',
                              Link.OTHER_STATEMENT)
        self.assertEqual(geometry.extent_reasons(layout, biopsy_sentence, extent),
                         (Reason.EXTENT_INFERRED,), "the ileum read from the biopsy's sentence is inferred")

    def test_w1s399_a_reach_cited_from_a_biopsy_sentence_is_inferred(self):
        # D36: the colonoscopy's extent is never stated ("advanced under direct vision"); a reach Gemini takes from
        # "Biopsies of the ascending colon were taken" is inferred from where an act was done, so R6 asks the extent
        layout = Layout.of(W1S399)
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),))
        colonoscopy = Anchor((unit_with(layout, 'The colonoscope was inserted and advanced'),), 'colonoscope',
                             'was inserted and advanced')
        egd = Anchor((unit_with(layout, 'Gastroscope passed under direct vision'),), 'Gastroscope', 'passed')
        biopsy = unit_with(layout, 'Biopsies of the ascending colon were taken')
        acts = (colonoscopy, egd, Anchor((biopsy,), 'Biopsies', 'were taken'),
                Anchor((unit_with(layout, 'Sigmoid colon, 30 cm'),), 'cold snare', 'removed en bloc'),
                Anchor((unit_with(layout, 'The polypectomy site was tattooed'),), 'tattooed', 'was tattooed'))
        extent = geometry.extent_units(layout, sections, tuple(Event(act, (), DONE) for act in acts), 0)
        reach = src((biopsy,), 'ascending colon', Link.OTHER_STATEMENT)
        self.assertEqual(geometry.extent_reasons(layout, reach, extent), (Reason.EXTENT_INFERRED,))
        session = geometry.session_subject(layout, sections, colonoscopy)
        self.assertEqual(geometry.link_reasons(layout, Sections(layout, ()), session,
                                               src((biopsy,), 'ascending colon')), (Reason.GEOMETRY_STATEMENT,),
                         'cited as the statement, G1 refuses it as well')
        upper = src((unit_with(layout, 'Gastroscope passed under direct vision'),), 'second part of the duodenum',
                    Link.OTHER_STATEMENT)
        self.assertEqual(geometry.extent_reasons(layout, upper, extent), (Reason.EXTENT_INFERRED,),
                         "another session's examination is another act")
        retroflexion = src((unit_with(layout, 'Retroflexion in the rectum'),), 'rectum', Link.OTHER_STATEMENT)
        self.assertEqual(geometry.extent_reasons(layout, retroflexion, extent), (),
                         'a sentence no act is told in')
        # the impression's "Normal-appearing duodenum, biopsied" restates an act of the EGD: a valid restatement
        impression = unit_with(layout, 'Normal-appearing duodenum, biopsied')
        restated = acts[:2] + (Anchor((unit_with(layout, 'duodenal'),), 'Biopsies', 'Biopsies'),)
        events = tuple(Event(act, (Restatement((impression,), RestatementRole.SUMMARIZES),) if position == 2 else (),
                             DONE) for position, act in enumerate(restated))
        duodenum = src((impression,), 'duodenum', Link.OTHER_STATEMENT)
        self.assertEqual(geometry.extent_reasons(layout, duodenum, geometry.extent_units(layout, sections, events, 1)),
                         (Reason.EXTENT_INFERRED,), "the EGD's reach read from an act's restatement (D198)")

    def test_a_reach_from_another_acts_restatement_is_inferred(self):
        # DECISIONS D198 (arbiter triage 1c#4): the impression line restates the biopsy; a reach read from it
        # is D36's hazard by another route. Before the ruling the restatement's unit was "the anchor of no act".
        layout = Layout.of(IMPRESSION)
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),
                                     Section('N1', src(('S4',), 'IMPRESSION', Link.SECTION), ())))
        examination = Anchor(('S2',), 'colonoscope', 'was inserted and advanced')
        biopsy = Anchor(('S3',), 'Biopsies', 'were taken')
        summary = Restatement(('S5',), RestatementRole.SUMMARIZES)
        self.assertTrue(geometry.restatement_valid(layout, sections, summary,
                                                   geometry.anchored_units((examination, biopsy))))
        events = (Event(examination, (), DONE), Event(biopsy, (summary,), DONE))
        extent = geometry.extent_units(layout, sections, events, 0)
        self.assertEqual(extent.acts, frozenset({'S3', 'S5'}))
        self.assertEqual(geometry.extent_reasons(layout, src(('S5',), 'Ascending colon', Link.OTHER_STATEMENT),
                                                 extent), (Reason.EXTENT_INFERRED,))
        self.assertEqual(geometry.extent_reasons(layout, src(('S3',), 'ascending colon', Link.OTHER_STATEMENT),
                                                 extent), (Reason.EXTENT_INFERRED,))
        # a restatement G6 ignores tells nothing: one on another event's anchor unit adds no unit of its own
        ignored = Event(biopsy, (Restatement(('S2',), RestatementRole.RESTATES),), DONE)
        self.assertEqual(geometry.extent_units(layout, sections, (events[0], ignored), 0).acts, frozenset({'S3'}))
        # a denial's restatement is a denial's too
        denied = (events[0], Event(biopsy, (summary,), DENIED))
        self.assertEqual(geometry.extent_reasons(layout, src(('S5',), 'Ascending colon', Link.OTHER_STATEMENT),
                                                 geometry.extent_units(layout, sections, denied, 0)), ())

    def test_a_denials_anchor_is_no_acts(self):
        # DECISIONS D198: "The terminal ileum was intubated and no biopsies were taken." is a reach sentence anchored
        # only by a denial. Before the ruling every event's anchor counted, and the reach was extent_inferred.
        layout = Layout.of(INTUBATION)
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),))
        examination = Anchor(('S1',), 'colonoscope', 'was advanced')
        denial = Anchor(('S2',), 'biopsies', 'no biopsies were taken')
        reach = src(('S2',), 'terminal ileum', Link.OTHER_STATEMENT)
        extent = geometry.extent_units(layout, sections, (Event(examination, (), DONE), Event(denial, (), DENIED)), 0)
        self.assertEqual(extent, geometry.Extent(own=frozenset({'S1'}), acts=frozenset()))
        self.assertEqual(geometry.extent_reasons(layout, reach, extent), ())
        for status in (DONE, FactState.CONTRADICTED, None):
            with self.subTest(status=status):
                told = geometry.extent_units(layout, sections, (Event(examination, (), DONE), Event(denial, (), status)),
                                             0)
                self.assertEqual(geometry.extent_reasons(layout, reach, told), (Reason.EXTENT_INFERRED,),
                                 'a status that is not negated, or none, is an act')

    def test_the_examinations_own_units_always_place_its_reach(self):
        layout = Layout.of(SHARED)
        sections = Sections(layout, (Section('N0', src((), '', Link.SECTION), ()),))
        examination = Event(Anchor(('S1',), 'colonoscope', 'was advanced'), (), DONE)
        biopsy = Event(Anchor(('S1',), 'biopsy', 'was taken'), (), DONE)
        cecum = src(('S1',), 'cecum')
        self.assertEqual(geometry.extent_reasons(layout, cecum, geometry.extent_units(
            layout, sections, (examination, biopsy), 0)), (), "the examination's sentence, though an act shares it")
        self.assertEqual(geometry.extent_reasons(layout, cecum, geometry.extent_units(
            layout, sections, (examination, biopsy), None)), (Reason.EXTENT_INFERRED,),
            'with no examination, a shared sentence is an act sentence')
        self.assertEqual(geometry.extent_reasons(layout, src(('S2',), 'prep'), geometry.extent_units(
            layout, sections, (examination, biopsy), None)), ())
        invalid = Event(Anchor(('S1',), 'gastroscope', 'was advanced'), (), DONE)
        self.assertEqual(geometry.locate_anchor(layout, invalid.anchor).reasons, (Reason.ANCHOR_WORDS,))
        self.assertEqual(geometry.extent_reasons(layout, cecum, geometry.extent_units(
            layout, sections, (invalid, biopsy), 0)), (Reason.EXTENT_INFERRED,),
            'an examination anchor that fails I3 places nothing: the biopsy is told there')
        self.assertEqual(geometry.extent_reasons(layout, cecum, geometry.extent_units(layout, sections, (invalid,), 0)),
                         (), 'the session\'s own examination is no act (D198), though its anchor places nothing')
        # the examination's valid restatement places its reach though another act's restatement shares the unit
        text = 'The colonoscope was advanced.\nA biopsy was taken.\n\nImpression: colonoscopy to the cecum with biopsy.\n'
        restated = Layout.of(text)
        both = Restatement(('S3',), RestatementRole.SUMMARIZES)
        events = (Event(Anchor(('S1',), 'colonoscope', 'was advanced'), (both,), DONE),
                  Event(Anchor(('S2',), 'biopsy', 'was taken'), (both,), DONE))
        none = Sections(restated, (Section('N0', src((), '', Link.SECTION), ()),))
        to_cecum = src(('S3',), 'cecum', Link.OTHER_STATEMENT)
        self.assertEqual(geometry.extent_reasons(restated, to_cecum, geometry.extent_units(restated, none, events, 0)),
                         ())
        alone = (Event(events[0].anchor, (), DONE), events[1])
        self.assertEqual(geometry.extent_reasons(restated, to_cecum, geometry.extent_units(restated, none, alone, 0)),
                         (Reason.EXTENT_INFERRED,), "without the examination's restatement it is the biopsy's")
        self.assertEqual(geometry.extent_units(restated, none, events, 7), geometry.Extent(
            own=frozenset(), acts=frozenset({'S1', 'S2', 'S3'})), 'a position outside the events names no examination')

    def test_where_the_words_lie_decides_and_an_unplaced_source_is_inferred(self):
        doc = Doc()
        extent = doc.extent()
        both = (doc.snare, doc.denial)
        self.assertEqual(geometry.extent_reasons(doc.layout, src(both, 'cold snare'), extent),
                         (Reason.EXTENT_INFERRED,), "the words lie only in the snare's anchor")
        self.assertEqual(geometry.extent_reasons(doc.layout, src(both, 'biopsy nor tattoo'), extent), (),
                         "the words lie only in the denials' anchor, which is no act's (D198)")
        self.assertEqual(geometry.extent_reasons(doc.layout, src((doc.denial, doc.frame), 'the endoscopy team'),
                                                 extent), ())
        self.assertEqual(geometry.extent_reasons(doc.layout, src(both, ''), extent), (),
                         'words "" lie in every cited unit')
        self.assertEqual(geometry.extent_reasons(doc.layout, src((doc.snare, doc.denial, doc.frame), ''), extent), ())
        self.assertEqual(geometry.extent_reasons(doc.layout, src((doc.findings,), 'the ileum'), extent),
                         (Reason.EXTENT_INFERRED,))
        self.assertEqual(geometry.extent_reasons(doc.layout, src(('S99',), ''), extent),
                         (Reason.EXTENT_INFERRED,))
        self.assertEqual(extent.own, frozenset({doc.findings}))
        self.assertNotIn(doc.denial, extent.acts)
        self.assertEqual(geometry.EXTENT_ATTRIBUTES[0].value, 'reached')
        self.assertEqual({attribute.value for attribute in geometry.EXTENT_ATTRIBUTES},
                         {'reached', 'completion', 'stations', 'approach', 'through'})


# --- every failure is a closed-list reason, and nothing raises --------------------------------------------------------


class PropertyTests(SimpleTestCase):
    @hypothesis.settings(max_examples=300, deadline=None, database=None)
    @hypothesis.given(st.data())
    def test_a_malformed_citation_is_a_reason_never_an_exception(self, data):
        doc = Doc()
        ids = st.sampled_from([unit.id for unit in doc.layout.units] + ['S0', 'S99', 'X1', ''])
        units = tuple(data.draw(st.lists(ids, max_size=14)))
        words = data.draw(st.one_of(st.text(max_size=12), st.sampled_from(['cold snare', 'Findings:', '', ' '])))
        link = data.draw(st.sampled_from(list(Link)))
        source = Source(units, words, link)
        anchor = Anchor(tuple(data.draw(st.lists(ids, max_size=3))), data.draw(st.text(max_size=6)),
                        data.draw(st.text(max_size=6)))
        found = geometry.bind_words(doc.layout, units, words)
        self.assertTrue(set(found.reasons) <= I_REASONS)
        self.assertEqual(found.reasons == (), found.span is not None and (found.place is not None))
        for subject in (doc.subject(anchor), geometry.unplaced_subject(),
                        geometry.section_subject(doc.sections, data.draw(st.sampled_from(['N0', 'N3', 'N9']))),
                        geometry.described_subject(doc.layout, doc.sections, source)):
            self.assertTrue(set(doc.links(subject, source)) <= G1_REASONS)
        self.assertTrue(set(geometry.target_reasons(doc.layout, anchor, source)) <= {Reason.TARGET_DETACHED})
        self.assertTrue(set(geometry.lesion_reasons(doc.layout, doc.sections, anchor, (), source, doc.anchored))
                        <= {Reason.TARGET_DETACHED})
        self.assertTrue(set(geometry.inherit_reasons(doc.sections, anchor)) <= {Reason.INHERIT_UNATTACHED})
        status = data.draw(st.sampled_from([None, *FactState]))
        events = doc.events + (Event(anchor, (Restatement(units, RestatementRole.SUMMARIZES),), status),)
        extent = geometry.extent_units(doc.layout, doc.sections, events,
                                       data.draw(st.one_of(st.none(), st.integers(-1, len(events)))))
        self.assertTrue(set(geometry.extent_reasons(doc.layout, source, extent)) <= {Reason.EXTENT_INFERRED})
        self.assertIn(geometry.restatement_valid(doc.layout, doc.sections, Restatement(units, RestatementRole.TITLE),
                                                 doc.anchored), (True, False))
        found_anchor = geometry.locate_anchor(doc.layout, anchor)
        self.assertTrue(set(found_anchor.reasons) <= I_REASONS | {Reason.ANCHOR_WORDS})

    @hypothesis.settings(max_examples=100, deadline=None, database=None)
    @hypothesis.given(st.data())
    def test_random_sections_never_raise_and_spans_never_overlap(self, data):
        doc = Doc()
        ids = st.sampled_from([unit.id for unit in doc.layout.units] + ['S99'])
        count = data.draw(st.integers(0, 6))
        given = []
        for index in range(count):
            start = src(tuple(data.draw(st.lists(ids, max_size=2))), data.draw(st.sampled_from(['', 'Nurse:', 'A'])),
                        Link.SECTION)
            ends = tuple(src(tuple(data.draw(st.lists(ids, min_size=1, max_size=1))), '', Link.SECTION)
                         for _ in range(data.draw(st.integers(0, 1))))
            given.append(Section(f'N{index}', start, ends))
        sections = Sections(doc.layout, given)
        spans = sorted(place.span for place in sections.places if place.span is not None)
        for before, after in zip(spans, spans[1:]):
            self.assertLessEqual(before.end, after.start)
        starts = [place.start for place in sections.places if place.start is not None]
        for place in sections.places:
            self.assertTrue(set(place.reasons) <= {Reason.SECTION_ORDER, Reason.SECTION_START_UNLOCATED})
            self.assertEqual(len(place.closers), len(place.end_units))
            if place.reasons:
                self.assertIsNone(place.span)
            else:
                # 1c#2: whatever the list's order, a span holds no other section's start
                self.assertFalse(place.span is not None
                                 and any(place.span.start < start < place.span.end for start in starts))

    def test_pure_and_repeatable(self):
        first, second = Doc(), Doc()
        self.assertEqual(first.sections.places, second.sections.places)
        self.assertEqual(geometry.bind_words(first.layout, (first.snare,), 'cold snare'),
                         geometry.bind_words(second.layout, (second.snare,), 'cold snare'))


# --- 5.7 measure 4 over the module ------------------------------------------------------------------------------------

STR_METHODS = frozenset(name for name in dir(str) if not name.startswith('_'))
TEXT_MODULES = ('re', 'regex', 'unicodedata', 'difflib', 'fnmatch')


def single_character_geometry(source: str) -> list:
    """FINAL-V2 5.7 measure 4's SingleCharacterGeometry, as step 1a's test reads it (step 6a writes the guard proper): no
    import of re (nor regex, unicodedata, difflib, fnmatch); no string literal longer than one character in a
    comparison; no str call but isspace, islower, isalnum, and find or rfind given a one-character literal."""
    tree, out = ast.parse(source), []
    for node in ast.walk(tree):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
        out += [f'imports {name}' for name in names if name.split('.')[0] in TEXT_MODULES]
        if isinstance(node, ast.Compare):
            for operand in (node.left, *node.comparators):
                out += [f'compares with {leaf.value!r} at line {node.lineno}' for leaf in ast.walk(operand)
                        if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str) and len(leaf.value) > 1]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STR_METHODS
              and node.func.attr not in ('isspace', 'islower', 'isalnum')):
            first = node.args[0] if node.args else None
            if not (node.func.attr in ('find', 'rfind') and isinstance(first, ast.Constant)
                    and isinstance(first.value, str) and len(first.value) == 1):
                out.append(f'calls .{node.func.attr}() at line {node.lineno}')
    return out


def no_word_lists(source: str) -> list:
    """FINAL-V2 5.7 measure 4's NoWordLists: no module-level tuple, list, set or dict of two or more string literals -
    in any module-level statement, and no set or frozenset made of a string's characters."""
    out = []
    for statement in ast.parse(source).body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)):
            continue
        for node in ast.walk(statement):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            items = ([*node.keys, *node.values] if isinstance(node, ast.Dict)
                     else getattr(node, 'elts', []) if isinstance(node, (ast.Tuple, ast.List, ast.Set)) else [])
            if sum(1 for item in items if isinstance(item, ast.Constant) and isinstance(item.value, str)) >= 2:
                out.append(f'a module-level word list at line {node.lineno}')
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('set', 'frozenset')
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                    and len(node.args[0].value) > 1):
                out.append(f'a module-level set of characters at line {node.lineno}')
    return out


class GuardTests(SimpleTestCase):
    def test_the_module_keeps_measure_4(self):
        source = GEOMETRY.read_text(encoding='utf-8')
        self.assertEqual(single_character_geometry(source), [])
        self.assertEqual(no_word_lists(source), [])

    def test_each_rule_refuses_a_planted_control(self):
        plants = {'import re\n': 'imports re', 'import unicodedata\n': 'imports unicodedata',
                  "def f(c):\n    return c == 'no'\n": "compares with 'no'",
                  "def f(c):\n    return c in ('no', 'x')\n": "compares with 'no'",
                  'def f(t, w):\n    return t.find(w)\n': 'calls .find()',
                  "def f(t):\n    return ''.join(t)\n": 'calls .join()',
                  'def f(t):\n    return t.split()\n': 'calls .split()',
                  "def f(t):\n    return t.startswith('No')\n": 'calls .startswith()',
                  'def f(t):\n    return t.lower()\n': 'calls .lower()',
                  'def f(xs, x):\n    return xs.index(x)\n': 'calls .index()'}
        for plant, expected in plants.items():
            with self.subTest(plant=plant.strip()):
                self.assertTrue(any(expected in finding for finding in single_character_geometry(plant)))
        for plant in ("MARKERS = ('no', 'not')\n", "TABLE = {'denied': 1, 'without': 2}\n",
                      "class K:\n    W = ['no', 'nor']\n", "DASHES = frozenset('-\u2010')\n"):
            with self.subTest(plant=plant.strip()):
                self.assertTrue(no_word_lists(plant))
        for control in ("def f(c):\n    return c == '_'\n", 'def f(t):\n    return t[0].isalnum()\n',
                        'R = {Link.FRAME: Reason.GEOMETRY_FRAME}\n', 'SIZE = 12\n', "LIMIT = ('.',)\n"):
            with self.subTest(control=control.strip()):
                self.assertEqual(single_character_geometry(control) + no_word_lists(control), [])

    def test_the_imports(self):
        tree = ast.parse(GEOMETRY.read_text(encoding='utf-8'))
        imported = sorted({alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                           for alias in node.names}
                          | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)})
        self.assertEqual(imported, ['__future__', 'collections.abc', 'dataclasses', 'studio.interpretation.contract',
                                    'studio.interpretation.contract.fold', 'studio.interpretation.contract.types'])
        self.assertEqual([alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                          and node.module == 'studio.interpretation.contract' for alias in node.names], ['segment'])


# --- the development documents, embedded byte for byte (each sha256 asserted by FixtureTests) -----------------------

# GI Note #8 (FRESH-1 set A, fresh/inputs/A/note8.txt): synthetic, 19,398 characters.
NOTE8_SHA256 = '25ef61e4bf743b70a99fea032a83a429bc6e954c89564ff4b53aaddf9ef00a85'
NOTE8 = """\
GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 1
DIVISION OF GASTROENTEROLOGY AND HEPATOLOGY / ADVANCED ENDOSCOPY
COLONOSCOPY AND THERAPEUTIC IBD ENDOSCOPY REPORT
Patient: Elena Brooks, 52-year-old woman
Date of service: November 8, 2026 | Procedure location: Advanced Endoscopy Unit
Endoscopist: E. Morgan, MD | Referring physician: R. Chen, MD
Procedure: High-definition ileocolonoscopy with therapeutic intervention and dysplasia surveillance
Reason for referral: Symptomatic ileocolonic anastomotic narrowing in established Crohn disease; surveillance for
colonic dysplasia; evaluation of iron-deficiency anemia
Clinical indication and interval history
The patient has longstanding ileocolonic Crohn disease diagnosed in 2005 and underwent a laparoscopic ileocecal
resection with a stapled side-to-side ileocolonic anastomosis in 2017 for medically refractory fibrostenotic disease.
She is currently maintained on vedolizumab infusions every eight weeks. Over the preceding four months, she has
developed intermittent postprandial cramping, bloating, and transient nausea, particularly after high-residue meals,
without sustained vomiting or inability to pass flatus. She reports two to three nonbloody stools per day. Her recent
hemoglobin was 10.6 g/dL with ferritin 12 ng/mL despite oral iron; fecal calprotectin was mildly elevated. There is
no current fever, overt gastrointestinal hemorrhage, or unintentional rapid weight loss.
MR enterography performed September 21, 2026 demonstrated a short, fixed narrowing at the ileocolonic
anastomosis with modest upstream neo-terminal ileal caliber change and without an abscess, fistula, phlegmon, or
high-grade obstruction. The narrowing was estimated at approximately 1 cm in length. The multidisciplinary IBD
service considered a trial of endoscopic balloon dilation reasonable, provided the endoscopic appearance showed no
deep ulceration or suspicion for malignancy. The examination was also requested for dysplasia surveillance given the
duration of colonic involvement and a remote history of an inflammatory polyp.
Pertinent records reviewed before the examination
A colonoscopy from January 2024 described a patent but narrowed ileocolonic anastomosis, mild neo-terminal ileal
ulceration, and a 4 mm rectal hyperplastic polyp that was removed at that earlier encounter. No dilation was carried
out in 2024. An outside upper endoscopy performed in March 2023 documented a Schatzki ring treated with
balloon dilation and gastric biopsies at that time. Those upper gastrointestinal interventions are historical only; no
esophagogastroduodenoscopy or other upper endoscopic procedure was performed on November 8, 2026.
Available prior pathology did not document dysplasia. The present report records only the lower gastrointestinal
examination and interventions performed today.
Preprocedure evaluation and consent
Medical history includes Crohn disease, prior ileocecal resection, iron-deficiency anemia, controlled hypertension,
and mild osteopenia. Prior abdominal surgery is limited to the bowel resection and an uncomplicated laparoscopic
cholecystectomy. Her medications include vedolizumab, lisinopril, ferrous gluconate, vitamin D, and as-needed
acetaminophen. She is not taking warfarin, a direct oral anticoagulant, aspirin, or a P2Y12 inhibitor. No known allergy
to latex or standard endoscopic sedation agents was reported. She denied any recent cardiopulmonary symptoms.
Airway and anesthetic assessment were completed by the anesthesia service; the patient was classified as ASA II.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 2
Risks, benefits, and alternatives were discussed in detail, including the particular risks of perforation or delayed
bleeding following dilation of a Crohn-related narrowing, bleeding after mucosal resection, incomplete excision or
recurrence of large colorectal lesions, missed dysplasia, aspiration, and cardiopulmonary events related to sedation.
The possibility that a lesion encountered today might require referral rather than immediate resection was reviewed.
Written informed consent was obtained. A formal time-out was completed immediately before insertion, verifying
patient identity, intended lower endoscopic procedure, planned potential dilation and resection, and consent.
Anesthesia, equipment, and quality measures
Monitored anesthesia care with propofol was administered and supervised by the anesthesia team, with continuous
electrocardiographic, oxygen saturation, blood-pressure, and ventilation monitoring. The endoscopist did not
administer or bill for a separate physician-directed moderate sedation service. A high-definition pediatric
colonoscope with water-jet capability was used, along with narrow-band imaging for lesion characterization, a
through-the-scope wire-guided dilation balloon, an electrosurgical snare, cold biopsy forceps, and a submucosal
injection catheter as indicated. No fluoroscopy was used.
Bowel preparation was adequate after washing and suctioning, with a Boston Bowel Preparation Scale score of 2 in
the proximal remnant colon, 3 in the transverse colon, and 3 in the left colon, total 8. Because of the prior ileocecal
resection, the native cecum and ileocecal valve are surgically absent; completion of the examination was confirmed
by direct identification and photodocumentation of the ileocolonic anastomosis and subsequent intubation of the
neo-terminal ileum after dilation. Photographs were obtained of the anastomosis before and after therapy, the ileal
mucosa, each lesion before and after intervention, and the location of the tattoo in relation to the unresected lesion.
Procedure technique and chronological findings
The patient was positioned in the left lateral decubitus position. Digital rectal examination showed normal sphincter
tone, no palpable mass, and no gross blood. The colonoscope was introduced through the anus and advanced
carefully under direct vision through the rectum, sigmoid, descending and transverse colon to the right-sided
ileocolonic anastomosis. Carbon-dioxide insufflation and water exchange were used to limit distention. Luminal
anatomy was consistent with prior ileocecal resection. The mucosa was inspected on insertion where necessary, and
a deliberate, segment-by-segment assessment was performed during withdrawal, with additional inspection of
visually abnormal areas using high-definition white-light imaging and narrow-band imaging.
Ileocolonic anastomosis and balloon dilation
At the right-sided ileocolonic anastomosis there was a single, short, concentric benign-appearing stenosis measuring
approximately 8-9 mm in luminal diameter and 9 mm in longitudinal extent. The anastomotic rim contained two
superficial erosions without deep excavation, mass effect, heaped edges, or active bleeding. The pediatric
colonoscope could not pass the narrowing initially with gentle pressure. The mucosal appearance was reviewed
carefully and no endoscopic feature suggested a malignant stricture. Two cold-forceps mucosal biopsies were taken
from an inflamed portion of the anastomotic rim and placed in a dedicated container.
A guidewire was passed under direct endoscopic vision through the stenosis into the neo-terminal ileum. A
through-the-scope controlled radial expansion balloon was advanced over the wire and centered across the
anastomotic narrowing. The balloon was inflated sequentially to 12 mm for 60 seconds, 13.5 mm for 60 seconds,
and 15 mm for 45 seconds, with complete deflation and inspection between stages. A superficial mucosal split was
observed at the final diameter, an expected dilation effect; there was no deep mural injury, transmural defect, or
significant hemorrhage. The balloon and guidewire were removed, and the colonoscope then traversed the treated
narrowing without resistance. The passage and patency of the dilated anastomosis were photographed. No colonic
stent was placed.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 3
Neo-terminal ileum and segmental mucosal sampling
The neo-terminal ileum was examined for approximately 15 cm beyond the anastomosis. Within its distal 8 cm there
were six discrete, 2- to 3-mm aphthous erosions with narrow erythematous halos, separated by intervening
normal-appearing villous mucosa. There was no deeper ulcer, spontaneous bleeding, or additional ileal narrowing.
Four targeted cold-forceps biopsies were obtained from representative inflamed ileal mucosa, away from the
dilation site. The proximal neo-terminal ileum was unremarkable. The postoperative appearance was consistent with
mild endoscopic recurrence of Crohn disease, corresponding descriptively to a modified Rutgeerts i2b pattern,
pending clinical correlation and histology.
During withdrawal, the colonic mucosa was examined with dye-free electronic chromoendoscopy. There were
isolated areas of mild loss of vascular pattern in the transverse colon and left colon, but no extensive confluent
ulceration or deep inflammatory lesions. Targeted cold-forceps biopsies were obtained from an erythematous patch
in the proximal transverse colon and, separately, from mildly granular rectosigmoid mucosa. These samples were
collected for assessment of inflammatory activity and dysplasia surveillance; they were not taken from any
subsequently resected polyp or the unresected suspicious lesion described below. The mucosal samples were placed
in separately designated pathology containers by location.
Distal transverse colon: endoscopic mucosal resection
In the distal transverse colon, approximately 58 cm from the anal verge, a 23 mm laterally spreading granular-type
lesion was identified on a fold, with a homogeneous regular surface and no ulceration, spontaneous bleeding, or
focal depression. High-definition and narrow-band imaging showed a pattern consistent with a superficial
noninvasive adenomatous or serrated lesion. A submucosal injection of approximately 7 mL of saline with dilute
methylene blue was placed directly beneath this distal transverse-colon lesion, resulting in a uniform, satisfactory
lift. The lift was performed solely to facilitate endoscopic mucosal resection of this lesion.
The lesion was resected using a 15 mm electrocautery snare in two overlapping pieces, encompassing all visible
neoplastic tissue. The two fragments were retrieved using a net and submitted together in one specimen container.
Careful inspection under white light and narrow-band imaging showed no visible residual polyp at the resection bed.
Minor oozing from the cut mucosal edge resolved with brief contact coagulation using the snare tip. The perimeter
of the resection defect was treated with low-power snare-tip soft coagulation as an adjunct to the same mucosal
resection, not as treatment of a separate lesion. Two through-the-scope clips were placed across the defect for
prophylactic closure; the clips were not used to treat a separate active bleeding source. No immediate bleeding or
deep mural injury was observed.
Splenic flexure: unresected lesion and localization tattoo
At the splenic flexure, approximately 48 cm from the anal verge, a separate 17 mm non-granular flat lesion with a
subtle centrally depressed area and focally distorted vascular pattern was identified. The surface appearance raised
concern for superficial submucosal invasion. In view of this morphology and the anticipated need for expert en bloc
assessment, this lesion was left in situ. No biopsy, snare resection, ablation, or balloon dilation was performed on
this splenic-flexure lesion during the present encounter.
For future localization, a sterile carbon-particle tattoo was placed in normal mucosa approximately 4 cm distal
(toward the anus) to the splenic-flexure lesion, on the opposite wall, using two separate submucosal injections of
approximately 0.6 mL each. The tattoo formed two visible submucosal blebs, and its relationship to the unresected
lesion was photographed. This tattoo was anatomically and procedurally distinct from the saline/methylene-blue lift
used for the mucosal resection in the distal transverse colon. No carbon-particle tattoo was placed into the
transverse-colon resection bed.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 4
Descending colon: separate cold-snare polypectomy
A separate 9 mm sessile polyp with a smooth surface was present in the mid-descending colon, approximately 35 cm
from the anal verge. The polyp was captured at its base with a cold snare and removed completely in one piece
without electrocautery. The specimen was retrieved and placed in its own pathology container. The post-resection
site was clean, without residual polyp tissue, significant bleeding, or a visible deep defect. Neither the dilation
balloon nor the EMR electrosurgical snare was used to treat this polyp. No clip or cautery was required at this site.
Remaining colon, rectum, and retroflexion
A few small-mouthed diverticula were seen in the sigmoid colon without associated inflammation or bleeding. One
flat 4 mm, nonbleeding vascular ectasia in the proximal rectum was photographed but not treated; there was no
oozing, adherent clot, or visible bleeding vessel. There were no additional polyps requiring removal. Retroflexion in
the rectum disclosed small, nonbleeding internal hemorrhoids and otherwise normal distal rectal anatomy. No
hemostatic cautery, hemostatic clipping, injection for bleeding, or band ligation was performed in the rectum. The
scope was withdrawn after a final inspection, and the patient tolerated the examination well.
Specimens submitted
Specimen A: neo-terminal ileum, targeted cold-forceps biopsies from aphthous erosions. Specimen B: inflamed
mucosa at the ileocolonic anastomotic rim, cold-forceps biopsies. Specimen C: proximal transverse-colon mucosa,
targeted cold-forceps biopsies for activity and dysplasia evaluation. Specimen D: distal transverse-colon lesion, two
fragments from the single endoscopic mucosal resection. Specimen E: descending-colon polyp, cold-snare removal
en bloc. Specimen F: rectosigmoid mucosa, targeted cold-forceps biopsies. No tissue was taken from the unresected
splenic-flexure lesion. Histopathology was pending at the time this report was finalized.
Technical outcome and immediate complications
The anastomotic narrowing was successfully dilated to 15 mm and subsequently traversed. The 23 mm distal
transverse-colon lesion was removed by piecemeal mucosal resection, and the separate 9 mm descending-colon
polyp was removed completely by cold snare. Both specimens were retrieved. Directed carbon-particle tattooing
successfully marked the distinct, unresected splenic-flexure lesion. There was no sustained intraprocedural bleeding,
endoscopically evident perforation, aspiration, anesthesia-related instability, or other immediate adverse event.
Estimated blood loss was minimal. A procedure time of 84 minutes reflected the detailed surveillance examination
and multiple therapeutic interventions; the patient was transferred to monitored recovery awake and
hemodynamically stable.
Postprocedure impression
1. Short fibrotic-appearing ileocolonic anastomotic stricture in a patient with postoperative Crohn disease,
successfully treated with wire-guided through-the-scope balloon dilation to 15 mm, with successful subsequent
intubation of the neo-terminal ileum.
2. Mild recurrent neo-terminal ileitis with scattered aphthous erosions and mild patchy colonic erythema, sampled by
targeted mucosal biopsy at sites separate from the therapeutic polypectomy and mucosal-resection lesions.
3. Distal transverse-colon 23 mm granular laterally spreading lesion, treated with saline-assisted piecemeal
endoscopic mucosal resection and prophylactic defect closure.
4. Distinct 17 mm non-granular splenic-flexure lesion with depressed morphology, intentionally not biopsied or
removed; carbon-particle tattoo placed distal and opposite the lesion for accurate future localization.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 5
5. Mid-descending-colon 9 mm sessile polyp, completely removed by cold-snare technique. Nonbleeding rectal
vascular ectasia, mild sigmoid diverticulosis, and small internal hemorrhoids were incidental findings and required no
therapy.
Recovery instructions and management plan
The patient may begin clear liquids after recovery and advance to a low-residue diet as tolerated for the next 48
hours, with particular attention to post-dilation discomfort, progressive abdominal distention, or persistent pain. She
was instructed to avoid nonsteroidal anti-inflammatory drugs unless specifically directed by her prescribing
physician. Written instructions reviewed signs requiring urgent evaluation, including sustained severe abdominal
pain, fever, hematochezia, melena, persistent vomiting, syncope, or inability to pass gas. Standard post-anesthesia
supervision and driving restrictions were discussed with the patient and accompanying adult.
Histology from all submitted specimens will be reviewed when available and incorporated into the IBD management
plan. The IBD team will reassess symptoms after dilation and discuss ongoing biologic treatment using pathology,
prior imaging, biomarkers, and clinical response; endoscopic dilation does not by itself establish resolution of active
inflammation. The 23 mm transverse-colon resection site will require surveillance to evaluate for residual or
recurrent tissue, with exact timing determined by histology and the multidisciplinary plan. The suspicious
splenic-flexure lesion will be reviewed by advanced endoscopy and colorectal surgery for consideration of en bloc
resection or other management after expert optical assessment; tattoo photographs and precise location will
accompany the referral.
The patient and her family were informed that the unresected splenic-flexure lesion requires timely further
evaluation and that no diagnosis of invasive cancer can be made from optical appearance alone. A future
intervention for that lesion is planned but was not performed at this encounter. The untreated rectal vascular
ectasia will be observed unless bleeding or another indication for therapy develops. The plan and immediate findings
were reviewed verbally before discharge, and a copy of the endoscopy report was forwarded to the referring IBD
clinician.
Attestation
I personally performed the lower gastrointestinal examination, reviewed the video and image documentation, and
carried out the tissue sampling, balloon dilation, mucosal resection, cold-snare polypectomy, and separate
localization tattooing described above. The procedures and outcomes recorded in the findings sections occurred
during the single date of service stated at the top of this report. Prior endoscopic procedures mentioned in the
history and possible future interventions described in the plan are not part of the services performed today.
E. Morgan, MD | Advanced Endoscopy and Inflammatory Bowel Disease
Electronically authenticated: November 8, 2026, 2:36 PM
"""

# D36's W1S-399 (FRESH-1 set C, fresh/inputs/C/W1S-399.txt): synthetic, 2,438 characters.
W1S399_SHA256 = 'eb38121d2ef6e6100904c9bccbe4447f7edc81ef1ff71e06db4592b4770d0c1f'
W1S399 = """\
SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE

ENDOSCOPY NOTE - EGD AND COLONOSCOPY, SAME SESSION
Patient: Synthetic Patient (fictional)    Age: 67    Sex: F
Service date: Oct 14, 2026
Endoscopist: Synthetic Endoscopist, MD (fictional)
Sedation: Propofol, administered by anesthesia (CRNA)
Instruments: Gastroscope; adult colonoscope

INDICATION
Iron deficiency anemia found on routine labs (hemoglobin 9.6 g/dL, ferritin
5 ng/mL). No melena and no visible blood. Takes aspirin 81 mg daily. Past
history: ERCP with biliary sphincterotomy and stone extraction at another
hospital in 2023, followed by laparoscopic cholecystectomy.

EGD
Consent confirmed and time-out done. Left lateral position, bite block
placed. Gastroscope passed under direct vision through the esophagus and
stomach to the second part of the duodenum.
Esophagus normal; Z-line at 38 cm. 2 cm sliding hiatal hernia without
Cameron lesions. Patchy erythema in the antrum, no erosions or ulcers.
Body and fundus normal, including on retroflexion.
Duodenal bulb and second portion normal. The major papilla shows a healed
sphincterotomy.
Biopsies, cold forceps: antrum and body for H. pylori (jar 1); duodenal
bulb and second portion for celiac disease (jar 2). The papilla was cannulated with a sphincterotome.

COLONOSCOPY
Bite block removed; she remained in the left lateral position. Rectal exam
normal. The colonoscope was inserted and advanced under direct vision. Prep
fair; brown liquid stool was washed and suctioned.
Sigmoid colon, 30 cm: 10 mm sessile polyp, removed en bloc with a cold
snare and retrieved (jar 3). Because she takes aspirin, one clip was
placed to close the defect; no bleeding was seen before or after.
Moderate diverticulosis in the sigmoid and descending colon.
Retroflexion in the rectum: small internal hemorrhoids.
The polypectomy site was tattooed with India ink.
Biopsies of the ascending colon were taken for microscopic colitis (jar 4).
Complications: none.

IMPRESSION
1. 2 cm hiatal hernia; mild antral erythema, biopsied.
2. Normal-appearing duodenum, biopsied for celiac disease.
3. Healed sphincterotomy at the papilla from the 2023 ERCP.
4. 10 mm sigmoid polyp removed with cold snare; prophylactic clip placed.
5. Diverticulosis of the sigmoid and descending colon.
6. Small internal hemorrhoids.

PLAN
- Ferrous sulfate 325 mg every other day; repeat CBC and ferritin in
  3 months.
- Continue aspirin.
"""
