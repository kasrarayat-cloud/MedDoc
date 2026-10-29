"""Session 7c8d38da, GI round 3, extent (gi3 extent): the shared extent and table interpretation, read by the SOURCE.

The second round's walk at 90377ec6f413 found three extent failures that every revision read the same way, each from a
shared reader, not from one document (interpretation 45):
- h2-01: "Procedure summary" over a Word table ("Examination | Instrument | Furthest point reached | Tissue sampled") was
  no heading and no reader understood a table, so "Indications" ran over the table and both services' parts: every
  statement read as an indication's, both services "uncertain", the extent asked twice;
- h2-02: "Deepest point reached:" was no extent label, and "could not be advanced past the hepatic flexure" read "past" as
  an earlier occasion, so the flexure was never reached;
- h2-04: "Procedure and findings" was no heading, so "Indications" ran over the report, and "pyloric channel" named no
  landmark.

The repairs (studio/gi/sections.py, cues.py, detect.py):
- the ONE table model (sections.tables, read here and by the documented-service inventory): a header row of three or
  more " | " cells, each a bare label (a letter first, at most five words, no digit, no sentence punctuation, no answer
  word), its first cell optionally a numbering column, over rows of as many cells;
- R1: a procedure-summary label straight over a summary table (an examination column, an extent column with an extent
  written in it, no dated row, and no line naming the table's service with an earlier occasion before the next heading)
  opens a procedure section; a table alone opens nothing;
- R2: a data cell that only answers a column that speaks neither for the row nor of a landmark or extent is a clause of
  its own (both sides);
- R3: a landmark that opens an extent column's cell is the row's extent label value, and a value in such a cell ends at
  the cell; a table's header row is column labels, never a landmark reach or an act;
- R4: one closed class of extent-label words for every reader, read in linear time; R5: "past the" is a place; R6:
  composite procedure/findings/technique headings; R7: the pyloric outlet is the stomach's; R8: a depth "of insertion" or
  measured from an anatomical anchor is part of the value; R9: a label in a reporting service part answers silently;
  N1: a short prepositional post-modifier may stand between an act and its post-negation.

Every corpus case (tests/corpus/gi3_extent) read right by the source is pinned right; every residual is pinned by its
exact output with its reason, so a change that fixes one fails loudly and is updated deliberately. Synthetic data only;
routing and the inventory are pure functions (no database, no provider).
"""
import json
import os
import time
import unittest
from datetime import date
from unittest import mock

from studio.gi import context as gi_context
from studio.gi import cues, detect, sections, services
from studio.gi.detect import route

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures', 'gi3')
CORPUS = os.path.join(HERE, 'corpus', 'gi3_extent', 'variants.json')
SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


def fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as fh:
        return fh.read()


def read(text: str, day=None):
    facts = gi_context.extract_context(text)
    if day is None:
        found = facts.get('service_date')
        day = date.fromisoformat(found.value) if found is not None and found.value else None
    return route(text, day), facts, day


def fact(finding, name):
    return next((x.value for x in finding.facts if x.name == name), None)


def reading(text: str, day=None) -> dict:
    """family -> (status, extent, interventions)."""
    r, _, _ = read(text, day)
    return {f.family: (f.status, fact(f, 'extent'), fact(f, 'interventions')) for f in r.findings}


def inventory(text: str, day=None):
    r, facts, day = read(text, day)
    return services.build(text, service_date=day, routing=r, context_facts=facts)


def cell_texts(text: str, table) -> list:
    return [[text[a:b] for a, b in row] for row in table.rows]


# --- the one table model ------------------------------------------------------------------------------------------

TABLED = SYNTHETIC + 'Report\n{}\nEnd of report.\n'


class TableModelTests(unittest.TestCase):
    """sections.tables: the rule exactly as the inventory's private copy implements it (the integration owner replaces
    that copy with this one after checking that the two agree on every corpus)."""

    def tables(self, body: str):
        text = TABLED.format(body)
        return text, sections.tables(text)

    def test_h2_01s_summary_table(self):
        text = fixture('h2-01__9468f9c1__2026-10-29.txt')
        found = sections.tables(text)
        self.assertIsInstance(found, tuple)
        self.assertEqual(len(found), 1)
        table = found[0]
        self.assertEqual(text[slice(*table.header)], 'Examination | Instrument | Furthest point reached | Tissue sampled')
        self.assertEqual(table.labels, ('examination', 'instrument', 'furthest point reached', 'tissue sampled'))
        self.assertEqual(cell_texts(text, table), [
            ['Upper endoscopy (EGD)', 'Standard gastroscope', 'Third portion of the duodenum', 'Yes, duodenum and stomach'],
            ['Colonoscopy', 'Adult colonoscope', 'Terminal ileum, about 6 cm beyond the ileocecal valve', 'No']])

    def test_a_numbering_column_comes_first(self):
        for first, label in (('#', '#'), ('No.', 'no'), ('No', 'no'), ('Item', 'item'), ('', ''), ('ITEM', 'item')):
            with self.subTest(first=first):
                text, found = self.tables(f'{first} | Examination | Extent\n1 | Colonoscopy | Cecum\n2 | EGD | Duodenum')
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0].labels, (label, 'examination', 'extent'))
                self.assertEqual(cell_texts(text, found[0]), [['1', 'Colonoscopy', 'Cecum'], ['2', 'EGD', 'Duodenum']])

    def test_a_numbering_column_is_only_the_first(self):
        for header in ('Examination | # | Extent', 'Examination | No | Extent', 'Examination | No. | Extent',
                       'Examination | Extent | '):
            with self.subTest(header=header):
                self.assertEqual(self.tables(header + '\nColonoscopy | 1 | Cecum')[1], ())

    def test_no_header_row(self):
        # a digit, an answer word, sentence punctuation, six words, a first character that is no letter, two cells
        for header in ('Examination | Size 5 mm | Extent', 'Examination | Extent | 2nd look', 'Examination | Yes | Extent',
                       'Yes | Examination | Extent', 'Examination | Extent | N/A', 'Examination | None | Extent',
                       'Examination | Extent | y', 'Examination | Biopsy? | Extent', 'Examination | Extent: | Biopsies',
                       'Examination | Notes. | Extent', 'Examination | Extent, depth | Biopsies',
                       'Examination | Extent | Biopsies taken today!', 'Examination | Extent | Biopsies; snares',
                       'Examination | the furthest point that was reached | Biopsies', '(Examination) | Extent | Biopsies',
                       '1 | Examination | Extent', 'Examination | Extent', 'Éxamen | Extent | Biopsies'):
            with self.subTest(header=header):
                self.assertEqual(self.tables(header + '\nColonoscopy | Cecum | No')[1], ())

    def test_two_cells_are_a_key_and_its_value(self):
        self.assertEqual(self.tables('Examination | Extent\nColonoscopy | Cecum\nEGD | Duodenum')[1], ())

    def test_five_words_are_a_label(self):
        text, found = self.tables('Examination | the furthest point thus reached | Biopsies\nColonoscopy | Cecum | No')
        self.assertEqual(found[0].labels, ('examination', 'the furthest point thus reached', 'biopsies'))

    def test_rows_have_as_many_cells(self):
        # a line with another count of cells ends the table: the row after it is no row of it (and "x | y | z", a header
        # row by its own shape, has no row under it)
        text, found = self.tables('Examination | Instrument | Extent\nColonoscopy | Scope | Cecum\nEGD | Scope\n'
                                  'x | y | z')
        self.assertEqual(len(found), 1)
        self.assertEqual(cell_texts(text, found[0]), [['Colonoscopy', 'Scope', 'Cecum']])
        text, found = self.tables('Examination | Instrument | Extent\n\nColonoscopy | Scope | Cecum')
        self.assertEqual(found, ())  # a blank line is a line of one cell

    def test_a_header_with_no_row_is_no_table(self):
        self.assertEqual(self.tables('Examination | Instrument | Extent\nThe colonoscope was advanced.')[1], ())

    def test_cells_split_exactly_on_the_separator(self):
        text, found = self.tables('Examination | Instrument | Extent\nColonoscopy |  | Cecum')
        self.assertEqual(cell_texts(text, found[0]), [['Colonoscopy', '', 'Cecum']])  # an empty cell is a cell
        for body in ('Examination|Instrument|Extent\nColonoscopy|Scope|Cecum',
                     'Examination\tInstrument\tExtent\nColonoscopy\tScope\tCecum',
                     '| Examination | Instrument | Extent |\n| Colonoscopy | Scope | Cecum |'):
            with self.subTest(body=body):
                self.assertEqual(self.tables(body)[1], ())

    def test_tables_in_document_order(self):
        text, found = self.tables('Examination | Instrument | Extent\nColonoscopy | Scope | Cecum\nThen:\n'
                                  'Lesion | Site | Removal\nPolyp | Sigmoid colon | Cold snare\nPolyp | Rectum | Forceps')
        self.assertEqual([t.labels for t in found], [('examination', 'instrument', 'extent'), ('lesion', 'site', 'removal')])
        self.assertLess(found[0].header[0], found[1].header[0])
        self.assertEqual(len(found[1].rows), 2)

    def test_the_layout_reads_the_same_tables(self):
        text = fixture('h2-01__9468f9c1__2026-10-29.txt')
        lay = sections.layout(text)
        self.assertEqual(lay.tables, sections.tables(text))
        self.assertEqual([(text[a:b], label) for a, b, label in lay.columns][:4],
                         [('Upper endoscopy (EGD)', 'examination'), ('Standard gastroscope', 'instrument'),
                          ('Third portion of the duodenum', 'furthest point reached'),
                          ('Yes, duodenum and stomach', 'tissue sampled')])
        header = text.index('Examination | Instrument')
        self.assertTrue(lay.in_table_header(header))
        self.assertIsNone(lay.column_at(header))  # a header's cells are no data cells
        self.assertFalse(lay.in_table_header(text.index('Upper endoscopy (EGD) |')))


# --- the known cases -------------------------------------------------------------------------------------------------

H2_01 = ('h2-01__9468f9c1__2026-10-29.txt', 'h2-01-endoscopy-report.txt')
H2_02 = ('h2-02__683c3e35__2026-10-29.txt', 'h2-02-colonoscopy-report.txt')
H2_04 = ('h2-04__3af9d4ce__2026-10-29.txt', 'h2-04-upper-endoscopy-report.txt')


class KnownCaseTests(unittest.TestCase):
    """The second round's acceptance failures, live and as their author wrote them, read by their source; and the
    known cases that must not move."""

    def test_h2_01_reads_both_extents(self):
        for name in H2_01:
            with self.subTest(name=name):
                text = fixture(name)
                got = reading(text)
                self.assertEqual(got['gi.egd'][:2], ('performed', 'third part of duodenum'))
                self.assertEqual(got['gi.colonoscopy'][:2], ('performed', 'terminal ileum'))
                kinds = [(s.kind, s.label) for s in sections.layout(text).sections]
                self.assertIn(('procedure', 'procedure summary'), kinds)  # the indication ends at the label
                colon = [(s.status, s.completion, s.extent) for s in inventory(text).services if s.family == 'gi.colonoscopy']
                self.assertEqual(colon, [('performed', 'complete', 'terminal ileum')])

    def test_h2_02_reads_the_flexure_and_keeps_the_earlier_sigmoidoscopy(self):
        for name in H2_02:
            with self.subTest(name=name):
                got = reading(fixture(name))
                self.assertEqual(got['gi.colonoscopy'][:2], ('incomplete', 'incomplete: hepatic flexure'))
                self.assertEqual(got['gi.flex_sig'][0], 'historical')  # "elsewhere on 2024-05-14"

    def test_h2_04_reads_the_stomach_no_dilation_and_the_planned_repeat(self):
        for name in H2_04:
            with self.subTest(name=name):
                text = fixture(name)
                r, _, _ = read(text)
                egd = r.finding('gi.egd')
                self.assertEqual((egd.status, fact(egd, 'extent')), ('incomplete', 'incomplete: stomach'))
                self.assertNotIn('dilation', fact(egd, 'interventions') or '')  # "was not attempted" (N1)
                repeat = text.index('upper endoscopy in about 8 weeks')
                self.assertEqual([m.status for m in egd.mentions if m.span.start == repeat], ['planned'])
                inv = [s for s in inventory(text).services if s.family == 'gi.egd']
                self.assertEqual([(s.status, s.extent) for s in inv], [('incomplete', 'incomplete: stomach')])
                self.assertFalse([a for a in inv[0].acts if a.kind == 'dilation' and a.status == 'performed'])

    def test_the_other_known_cases_are_unchanged(self):
        with open(os.path.join(FIXTURES, 'unchanged-readings.json'), encoding='utf-8') as fh:
            recorded = json.load(fh)['readings']
        self.assertEqual(len(recorded), 10)  # ho-01..ho-04, h2-03 and h2-05, live and author texts
        for name, expected in sorted(recorded.items()):
            with self.subTest(name=name):
                text = fixture(name)
                self.assertEqual([[s.kind, s.label, s.start] for s in sections.layout(text).sections], expected['sections'])
                self.assertEqual({family: list(values) for family, values in reading(text).items()}, expected['routing'])
                self.assertEqual(sorted([s.family, s.status, s.completion, s.extent] for s in inventory(text).services),
                                 expected['inventory'])


# --- the source-reviewed corpus --------------------------------------------------------------------------------------

def judge(expected: dict, got: dict) -> list:
    """The mismatches of a reading (family -> (status, extent, interventions)) with a case's source-reviewed facts."""
    bad = []
    for family, want in expected.items():
        if family == 'not_today':
            bad += [f'{other} read {got[other][0]}' for other in want
                    if other in got and got[other][0] in ('performed', 'incomplete')]
            continue
        if family not in got:
            bad.append(f'{family} absent')
            continue
        status, extent, interventions = got[family]
        if 'status_in' in want and status not in want['status_in']:
            bad.append(f'{family} status {status}')
        if 'extent' in want and extent != want['extent']:
            bad.append(f'{family} extent {extent!r}')
        bad += [f'{family} interventions {interventions!r}' for word in want.get('interventions_excludes', ())
                if word in (interventions or '')]
    return bad


# The residuals, each pinned by its exact reading (family -> (status, extent, interventions)) and its reason. Each one
# leaves the extent unread, so it is asked; none reads a wrong extent value.
KNOWN_LIMITS = {
    'F1-04-h201-ocr': ({'gi.office_em': ('planned', None, None), 'gi.egd': ('uncertain', None, None),
                        'gi.colonoscopy': ('uncertain', None, None)},
                       'OCR lost the bars: no table, so the summary label opens nothing and the indication runs on'),
    'F1-06-no-summary-heading': ({'gi.office_em': ('planned', None, None), 'gi.egd': ('uncertain', None, None),
                                  'gi.colonoscopy': ('uncertain', None, None)},
                                 'a table with no summary label is no evidence of today: it stays the indication\'s'),
    'F2-03-deepest-point-label-only': ({'gi.colonoscopy': ('incomplete', None, None),
                                        'gi.flex_sig': ('historical', None, None)},
                                       'an open identification clause after the value (", identified by ...") leaves '
                                       'the label unread'),
    'F2-11-label-value-wrapped': ({'gi.colonoscopy': ('performed', None, None), 'gi.flex_sig': ('historical', None, None)},
                                  'a label and its value on separate lines are no label'),
    'F2-11b-ocr-hyphen-wrap': ({'gi.colonoscopy': ('incomplete', None, None), 'gi.flex_sig': ('historical', None, None)},
                               'OCR hyphenated the landmark across lines ("hep-" / "atic flexure")'),
    'F4-02-two-services-one-line': ({'gi.egd': ('performed', None, None), 'gi.colonoscopy': ('performed', None, None)},
                                    'terse service parts with no act predicate ("EGD to D2") open no part of their '
                                    'own, so the indication holds their shorthand extents'),
    'F4-03c-table-ocr': ({'gi.egd': ('performed', None, None), 'gi.colonoscopy': ('uncertain', None, None)},
                         'OCR columns as spaces: no table'),
    'F4-04-table-colon-short': ({'gi.egd': ('performed', 'second part of duodenum', None),
                                 'gi.colonoscopy': ('incomplete', None, None)},
                                'a reason aside in the extent cell ("(looping)") leaves the value unplain'),
    'F7-h209': ({'gi.egd': ('uncertain', 'incomplete: esophagus', None), 'gi.eus': ('incomplete', None, None)},
                'h2-09 (EUS): no source-reviewed expectation in this lens; its routing is recorded only'),
    'F7-h210': ({'gi.ercp': ('performed', None, 'stent placement')},
                'h2-10 (ERCP): no source-reviewed expectation in this lens; its routing is recorded only'),
}


class CorpusTests(unittest.TestCase):
    """Every source-reviewed case: read right by its source, or a recorded residual read exactly as recorded."""

    @classmethod
    def setUpClass(cls):
        with open(CORPUS, encoding='utf-8') as fh:
            corpus = json.load(fh)
        cls.variants = corpus['variants']

    def test_the_corpus(self):
        self.assertEqual(len(self.variants), 89)
        self.assertLessEqual(set(KNOWN_LIMITS), {v['id'] for v in self.variants})
        for variant in self.variants:
            self.assertTrue(variant['text'].startswith('SYNTHETIC TEST DOCUMENT'))
            with self.subTest(case=variant['id']):
                got = reading(variant['text'])
                if variant['id'] in KNOWN_LIMITS:
                    self.assertEqual(got, KNOWN_LIMITS[variant['id']][0], KNOWN_LIMITS[variant['id']][1])
                else:
                    self.assertEqual(judge(variant['expected'], got), [], variant['review'])

    def test_every_residual_is_asked_never_valued_wrong(self):
        expected = {v['id']: v['expected'] for v in self.variants}
        for case, (got, _) in KNOWN_LIMITS.items():
            for family, (_, extent, _) in got.items():
                want = expected[case].get(family, {})
                with self.subTest(case=case, family=family):
                    self.assertIn(extent, (None, want.get('extent', extent)), f'{case}: {family} reads a wrong extent')


# --- R4: the label class -----------------------------------------------------------------------------------------------

COLON = SYNTHETIC + """Cedar Point Endoscopy (fictional)
Colonoscopy Report
Date of service: 2026-10-14
Place of service: ambulatory surgery center (POS 24)
Indication
Positive fecal immunochemical test.
Description of the procedure
{body}
Impression
{impression}
"""
DAY = date(2026, 10, 14)


def extent(text: str, family: str, day=None):
    return reading(text, day).get(family, (None, None, None))[1]


def status(text: str, family: str, day=None):
    return reading(text, day).get(family, (None, None, None))[0]


class LabelClassTests(unittest.TestCase):
    """R4: every wording of the closed class reads its landmark; aims, denials, times and verb phrases stay unread."""

    LABELS = ('Deepest point reached', 'Furthest point reached', 'Most proximal point reached', 'Most proximal extent',
              'Maximal insertion', 'Maximum insertion', 'Reached', 'Landmark reached', 'Furthest landmark reached',
              'Level reached', 'Insertion depth', 'Point reached', 'Extent', 'Extent of examination', 'Depth reached',
              'Farthest point', 'Insertion extent')

    def test_each_label_reads_its_landmark(self):
        for label in self.LABELS:
            for value, expected in (('hepatic flexure', 'incomplete: hepatic flexure'), ('cecum', 'cecum')):
                with self.subTest(label=label, value=value):
                    text = COLON.format(body=f'{label}: {value}.\nA 5 mm rectal polyp was removed with a cold snare.',
                                        impression='See above.')
                    self.assertEqual(extent(text, 'gi.colonoscopy', DAY), expected)

    def test_a_two_cell_row_is_a_label(self):
        for label in ('Extent', 'Deepest point reached', 'Reached'):
            with self.subTest(label=label):
                text = COLON.format(body=f'{label} | Hepatic flexure\nA 5 mm rectal polyp was removed with a cold snare.',
                                    impression='See above.')
                self.assertEqual(extent(text, 'gi.colonoscopy', DAY), 'incomplete: hepatic flexure')

    def test_aims_denials_and_times_stay_unread(self):
        for body, expected in (
                ('Intended extent: cecum.\nThe colonoscope was advanced to the hepatic flexure; the cecum was not reached.',
                 'incomplete: hepatic flexure'),
                ('Intended point reached: cecum.\nThe colonoscope was advanced to the hepatic flexure; the cecum was not '
                 'reached.', 'incomplete: hepatic flexure'),
                ('Extent: cecum (not reached).\nThe colonoscope was advanced to the transverse colon, where a mass '
                 'prevented further passage.', 'incomplete: transverse colon'),
                ('Insertion time: 3 minutes. The colonoscope was advanced to the cecum.', 'cecum')):
            with self.subTest(body=body):
                self.assertEqual(extent(COLON.format(body=body, impression='See above.'), 'gi.colonoscopy', DAY), expected)

    def test_a_depth_of_insertion_or_an_anchored_depth_is_part_of_the_value(self):  # R8
        for value in ('hepatic flexure, at about 95 cm of insertion', 'hepatic flexure, about 95 cm of insertion',
                      'hepatic flexure (95 cm insertion)'):
            with self.subTest(value=value):
                text = COLON.format(body=f'Deepest point reached: {value}.\nThe cecum was not examined.',
                                    impression='See above.')
                self.assertEqual(extent(text, 'gi.colonoscopy', DAY), 'incomplete: hepatic flexure')
        for value in ('Terminal ileum, about 6 cm beyond the ileocecal valve', 'Terminal ileum, 5 cm past the ileocecal valve'):
            with self.subTest(value=value):
                text = COLON.format(body=f'Procedure | Extent | Biopsies\nColonoscopy | {value} | No',
                                    impression='See above.')
                self.assertEqual(extent(text, 'gi.colonoscopy', DAY), 'terminal ileum')

    def test_verbal_labels_are_not_in_the_class(self):
        # "Advanced to:" is a verb phrase, not a label of the class: unread, as installed (a known limit)
        text = COLON.format(body='Advanced to: cecum.\nA 5 mm rectal polyp was removed with a cold snare.',
                            impression='See above.')
        self.assertIsNone(extent(text, 'gi.colonoscopy', DAY))

    def test_the_report_field_reader_shares_the_class(self):
        for line in ('Deepest point reached: cecum', 'Insertion depth: 30 cm', 'Extent reached: cecum', 'Reached: cecum'):
            with self.subTest(line=line):
                self.assertEqual(bool(sections._S2_REPORT_FIELD.match(line)), line != 'Reached: cecum')
        self.assertIsNone(sections._S2_REPORT_FIELD.match('Advanced to: cecum'))


# --- R5: "past the" is a place ----------------------------------------------------------------------------------------

UPPER_DAY = date(2026, 10, 7)
EGD_REPORT = SYNTHETIC + """Quillan Bend Surgical Center (fictional)
Upper Endoscopy Report
Date of service: 2026-10-07
Indications
Dyspepsia.
Findings
{body}
Impression
See above.
"""


class PastThePlaceTests(unittest.TestCase):
    """R5: "past the <landmark>" is a place, as "beyond the" always was; every time use keeps its reading."""

    def test_a_failed_advance_past_a_landmark_reaches_it(self):
        for word in ('past', 'beyond'):
            with self.subTest(word=word):
                text = COLON.format(body=f'The colonoscope could not be advanced {word} the splenic flexure despite '
                                         'position changes. The transverse colon, ascending colon and cecum were not '
                                         'examined.', impression='Incomplete colonoscopy.')
                self.assertEqual(extent(text, 'gi.colonoscopy', DAY), 'incomplete: splenic flexure')

    def test_past_as_a_time_stays_a_time(self):
        text = COLON.format(body='In the past year she had a flexible sigmoidoscopy elsewhere. Her past colonoscopy, in '
                                 '2019, was normal. Today the colonoscope was advanced to the cecum and the terminal '
                                 'ileum was intubated.', impression='Normal colonoscopy.')
        got = reading(text, DAY)
        self.assertEqual(got['gi.flex_sig'][0], 'historical')
        self.assertEqual(got['gi.colonoscopy'][1], 'terminal ileum')

    def test_past_before_a_comma_stays_a_time(self):
        # "past" then a comma is no place: "years past, a colonoscopy" names an earlier occasion
        text = EGD_REPORT.format(body='The gastroscope was advanced to the second portion of the duodenum. In years past, '
                                      'a colonoscopy found two adenomas.')
        got = reading(text, UPPER_DAY)
        self.assertEqual(got['gi.egd'][:2], ('performed', 'second part of duodenum'))
        self.assertEqual(got['gi.colonoscopy'][0], 'historical')


# --- R1 to R3: tables ---------------------------------------------------------------------------------------------------

TABLE = SYNTHETIC + """Northgate Endoscopy (fictional)
Bidirectional Endoscopy Report
Date of procedure: 2026-10-20
Place of service: ambulatory surgery center (POS 24)
Indications
Iron deficiency anemia.
{heading}{table}
{after}
"""
DAY20 = date(2026, 10, 20)
SUMMARY = ('Examination | Instrument | Furthest point reached | Tissue sampled\n'
           'Upper endoscopy (EGD) | Gastroscope | Second portion of the duodenum | Yes\n'
           'Colonoscopy | Colonoscope | Terminal ileum | No')


class TableTests(unittest.TestCase):
    """R1-R3 and the controls a table must keep."""

    def test_a_summary_label_over_the_table_opens_a_procedure_section(self):
        for label in ('Procedure summary', 'Summary of procedures', 'PROCEDURE SUMMARY', 'Procedure summary:',
                      '**Procedure summary**', 'Procedures overview'):
            with self.subTest(label=label):
                text = TABLE.format(heading=label + '\n', table=SUMMARY, after='Impression\nNormal examinations.')
                got = reading(text, DAY20)
                self.assertEqual(got['gi.egd'][:2], ('performed', 'second part of duodenum'))
                self.assertEqual(got['gi.colonoscopy'][:2], ('performed', 'terminal ileum'))

    def test_a_numbered_summary_table(self):
        for first in ('#', 'No.', 'Item', ''):
            with self.subTest(first=first):
                table = (f'{first} | ' + SUMMARY.split('\n')[0] + '\n1 | ' + SUMMARY.split('\n')[1] + '\n2 | '
                         + SUMMARY.split('\n')[2])
                text = TABLE.format(heading='Procedure summary\n', table=table, after='Impression\nNormal examinations.')
                got = reading(text, DAY20)
                self.assertEqual(got['gi.egd'][:2], ('performed', 'second part of duodenum'))
                self.assertEqual(got['gi.colonoscopy'][:2], ('performed', 'terminal ileum'))

    def test_a_table_only_extent_is_bound_to_its_row(self):
        text = TABLE.format(heading='Procedures performed\n',
                            table='Procedure | Extent | Biopsies\nEGD | Second portion of the duodenum | Yes\n'
                                  'Colonoscopy | Cecum | No',
                            after='Findings\nGastric antral erythema, biopsied. Normal colon.')
        got = reading(text, DAY20)
        self.assertEqual(got['gi.egd'][1], 'second part of duodenum')
        self.assertEqual(got['gi.colonoscopy'][:2], ('performed', 'cecum'))

    def test_an_answer_cell_answers_its_own_column_on_both_sides(self):
        for value, expected in (('Cecum', ('performed', 'cecum')),
                                ('Hepatic flexure', ('incomplete', 'incomplete: hepatic flexure'))):
            with self.subTest(value=value):
                text = TABLE.format(heading='Procedure summary\n',
                                    table=f'Examination | Biopsies | Furthest point reached\nColonoscopy | No | {value}',
                                    after='Impression\nSee the table; the cecum was not reached.' if value != 'Cecum'
                                    else 'Impression\nNormal colonoscopy.')
                got = reading(text, DAY20)
                self.assertEqual(got['gi.colonoscopy'][:2], expected)
                self.assertIsNone(got['gi.colonoscopy'][2])  # "Biopsies" names a column, "No" answers it: no biopsy

    def test_a_header_row_names_columns(self):
        # a landmark in a header is no reach ("Extent | Terminal ileum intubated" read as a two-cell label reached the
        # terminal ileum), and an act in it is no act done
        text = TABLE.format(heading='Procedures performed\n',
                            table='Examination | Extent | Terminal ileum intubated\nColonoscopy | Cecum | No',
                            after='Impression\nCecum reached; the terminal ileum was not intubated.')
        self.assertNotEqual(extent(text, 'gi.colonoscopy', DAY20), 'terminal ileum')
        text = TABLE.format(heading='Procedure summary\n',
                            table='Examination | Biopsies | Furthest point reached\nColonoscopy | No | Cecum',
                            after='Impression\nNormal colonoscopy.')
        self.assertIsNone(reading(text, DAY20)['gi.colonoscopy'][2])

    def test_a_label_in_another_cell_reads_its_tail_across_the_row(self):
        # only an extent column's cell ends its value (interpretation 45); a label written in another cell reads the next
        # cells as before (round 4c declared:11), so their denial or doubt still leaves it unread
        for row in ('Colonoscopy | Extent: cecum | Reached: No', 'Colonoscopy | Extent: cecum | Incomplete (poor preparation)'):
            with self.subTest(row=row):
                text = TABLE.format(heading='Procedures performed\n', table='Examination | Details | Status\n' + row,
                                    after='Impression\nSee above.')
                self.assertIsNone(extent(text, 'gi.colonoscopy', DAY20))

    def test_known_limit_a_table_without_its_label_stays_in_the_indication(self):
        # A table alone is no evidence that it is today's (an office note's undated outside table reads so too): with no
        # procedure-summary label over it, it stays the indication's and its services are asked, as installed.
        text = TABLE.format(heading='', table=SUMMARY, after='Impression\nNormal examinations.')
        self.assertEqual(reading(text, DAY20)['gi.egd'][:2], ('uncertain', None))

    def test_an_office_notes_outside_table_is_no_procedure(self):
        text = SYNTHETIC + ('Harbor View Gastroenterology (fictional)\nOffice Visit - progress note\nDate of service: '
                            '2026-10-21\nPlace of service: office (POS 11)\nVisit type: established patient\nReason for '
                            'visit\nReview of outside records.\nExamination | Instrument | Furthest point reached\n'
                            'Colonoscopy | Adult colonoscope | Cecum\nThe outside colonoscopy above was reviewed with the '
                            'patient.\nAssessment and plan\nRepeat in 3 years. Medical decision making: low.\n')
        self.assertNotIn(status(text, 'gi.colonoscopy', date(2026, 10, 21)), ('performed', 'incomplete'))

    def test_the_summary_label_needs_an_extent_column_and_undated_rows(self):
        # an office note's "Procedure summary" of what is planned names no extent; a dated row is a planned or an
        # earlier procedure ("Upper endoscopy (EGD) on <date>" reads its date for "EGD" alone: X2, the dates owner's)
        office = SYNTHETIC + ('Harbor View Gastroenterology (fictional)\nOffice Visit - progress note\nDate of service: '
                              '2026-10-21\nPlace of service: office (POS 11)\nReason for visit\nDysphagia.\n'
                              'Procedure summary\nExamination | Indication | Preparation\nUpper endoscopy (EGD) | '
                              'Dysphagia | Fasting\nAssessment and plan\nEGD to be booked. Medical decision making: low.\n')
        self.assertEqual(status(office, 'gi.egd', date(2026, 10, 21)), 'planned')
        # a landmark in another column is no extent written ("Lesion site"): a pre-procedure note's booked colonoscopy
        booked = SYNTHETIC + ('Marlowe Bay Endoscopy Suites (fictional)\nPre-procedure note\nDate of service: 2026-10-20\n'
                              'Indications\nPolyp follow-up.\nProcedure summary\nExamination | Indication | Lesion site\n'
                              'Colonoscopy | Polyp follow-up | Sigmoid colon\nPlan\nColonoscopy is booked for 2026-11-12.\n')
        self.assertEqual(status(booked, 'gi.colonoscopy', DAY20), 'planned')
        dated = TABLE.format(heading='Procedure summary\n',
                             table='Examination | Planned date | Furthest point reached\n'
                                   'Upper endoscopy (EGD) | 2026-11-12 | Second portion of the duodenum',
                             after='Plan\nBooked for 2026-11-12.')
        self.assertNotIn(status(dated, 'gi.egd', DAY20), ('performed', 'incomplete'))

    def test_the_summary_label_needs_an_examination_column(self):
        # an office note's summary of an outside report's findings names no examination per row: no procedure section, so
        # the colonoscopy the note talks about is not read as done today (with the section: performed, extent cecum)
        office = SYNTHETIC + ('Harbor View Gastroenterology (fictional)\nOffice Visit - progress note\nDate of service: '
                              '2026-10-21\nPlace of service: office (POS 11)\nVisit type: established patient\nReason for '
                              'visit\nReview of an outside report.\nProcedure summary\nFinding | Location | Furthest point '
                              'reached\nNormal mucosa | Colon | Cecum\n{line}\nAssessment and plan\n{plan} Medical decision '
                              'making: low.\n')
        findings = office.format(line='Colonoscopy findings were discussed with the patient.', plan='Repeat in 3 years.')
        self.assertEqual(reading(findings, date(2026, 10, 21))['gi.colonoscopy'][:2], ('uncertain', None))
        reviewed = office.format(line='Colonoscopy was reviewed with the patient.', plan='Repeat colonoscopy in 3 years.')
        self.assertEqual(reading(reviewed, date(2026, 10, 21))['gi.colonoscopy'][:2], ('planned', None))

    def test_the_summary_label_needs_an_extent_written(self):
        # a pre-procedure note's summary form with its extent column blank is no summary of a procedure done: the booked
        # colonoscopy stays planned (as at 90377ec6f413); the investigated design read it performed
        for cell in ('-', '', 'To be recorded', 'N/A'):
            with self.subTest(cell=cell):
                text = SYNTHETIC + ('Marlowe Bay Endoscopy Suites (fictional)\nPre-procedure note\nDate of service: '
                                    '2026-10-20\nPlace of service: ambulatory surgery center (POS 24)\nIndications\nIron '
                                    'deficiency anemia.\nProcedure summary\nExamination | Instrument | Furthest point '
                                    f'reached\nColonoscopy | Adult colonoscope | {cell}\nPlan\nColonoscopy is booked for '
                                    '2026-11-12.\n')
                self.assertEqual(status(text, 'gi.colonoscopy', DAY20), 'planned')
        for cell in ('35 cm', 'About 40 cm'):
            with self.subTest(cell=cell):  # a depth is an extent written: the summary opens
                text = SYNTHETIC + ('Northgate Endoscopy (fictional)\nFlexible Sigmoidoscopy Report\nDate of service: '
                                    '2026-10-20\nIndications\nRectal bleeding.\nProcedure summary\nExamination | Instrument | '
                                    f'Depth of insertion\nFlexible sigmoidoscopy | Sigmoidoscope | {cell}\nImpression\n'
                                    'Internal hemorrhoids.\n')
                self.assertIn(('procedure', 'procedure summary'),
                              [(s.kind, s.label) for s in sections.layout(text).sections])
                # Known limit: a column binds a landmark, never a depth, so the depth is not read (asked), as at
                # 90377ec6f413
                self.assertEqual(reading(text, DAY20)['gi.flex_sig'][:2], ('performed', None))

    def test_an_outside_report_pasted_into_an_office_note_is_no_summary(self):
        # the summary's own service named with an earlier occasion below the table: the outside colonoscopy stays
        # historical (as at 90377ec6f413); the investigated design read it performed today, extent cecum
        text = SYNTHETIC + ('Harbor View Gastroenterology (fictional)\nOffice Visit - progress note\nDate of service: '
                            '2026-10-21\nPlace of service: office (POS 11)\nVisit type: established patient\nReason for '
                            'visit\nReview of outside records.\nProcedure summary\nExamination | Instrument | Furthest point '
                            'reached\nColonoscopy | Adult colonoscope | Cecum\nThe outside colonoscopy above was reviewed '
                            'with the patient.\nAssessment and plan\nRepeat in 3 years. Medical decision making: low.\n')
        self.assertEqual(status(text, 'gi.colonoscopy', date(2026, 10, 21)), 'historical')

    def test_an_office_notes_bare_summary_table_is_asked(self):
        # gi3 integration (sections._office_titled): an office note's "Procedure summary" over an undated table with an
        # extent, and nothing that says whose or when, opens no procedure section, so the colonoscopy reads uncertain
        # and is asked, as at 90377ec6f413 (built, the label read it performed today, extent cecum). The same label and
        # table under a procedure report's title, or under a head line naming another occurrence's visit, still opens.
        # "Indications" closes the section a report's title opens (as h2-01's does), so only the label can open one here
        body = ('Indications\nSurveillance of adenomas.\nProcedure summary\nExamination | Instrument | Furthest point '
                'reached\nColonoscopy | Adult colonoscope | Cecum\nAssessment and plan\nRepeat in 3 years. Medical '
                'decision making: low.\n')
        head = ('Harbor View Gastroenterology (fictional)\n{title}\nDate of service: 2026-10-21\nPlace of service: office '
                '(POS 11)\nVisit type: established patient\n')
        for title, expected in (('Office Visit - progress note', ('uncertain', None)),
                                ('Clinic note - return visit', ('uncertain', None)),
                                ('Colonoscopy report', ('performed', 'cecum')),
                                ('Colonoscopy report\nScheduled clinic visit - in 3 months', ('performed', 'cecum'))):
            with self.subTest(title=title):
                text = SYNTHETIC + head.format(title=title) + body
                self.assertEqual(reading(text, date(2026, 10, 21))['gi.colonoscopy'][:2], expected)

    def test_an_office_title_below_the_head_is_no_office_note(self):
        # the title is read in the document's head only (context.TITLE_LINES non-blank lines), as routing reads it
        filler = ''.join(f'Line {n} of the report header.\n' for n in range(12))
        text = SYNTHETIC + 'Colonoscopy report\n' + filler + 'Office visit - progress note\n' + (
            'Indications\nSurveillance of adenomas.\nProcedure summary\nExamination | Instrument | Furthest point '
            'reached\nColonoscopy | Adult colonoscope | Cecum\nImpression\nNormal.\n')
        self.assertEqual(reading(text, date(2026, 10, 21))['gi.colonoscopy'][:2], ('performed', 'cecum'))

    def test_an_answer_about_a_landmark_or_the_extent_stays_with_its_row(self):
        # "Cecum reached | No" says the reach fell short, "Furthest point reached | None" that nothing was reached: such an
        # answer speaks of the row's reach, so it keeps doubting the row (asked), never cut away into a clean reach
        # (a label with a performance word, "Cecum reached", "Furthest point reached", speaks for the row anyway)
        contra = TABLE.format(heading='Procedure summary\n',
                              table='Examination | Extent | Terminal ileum\nColonoscopy | Terminal ileum | No',
                              after='Impression\nSee above.')  # the row contradicts itself: asked, never the ileum
        self.assertIsNone(extent(contra, 'gi.colonoscopy', DAY20))
        nothing = TABLE.format(heading='Procedure summary\n',
                               table='Examination | Instrument | Extent\nUpper endoscopy (EGD) | Gastroscope | Second portion '
                                     'of the duodenum\nColonoscopy | Colonoscope | None',
                               after='Impression\nSee above.')  # the EGD row writes an extent, so the summary opens
        got = reading(nothing, DAY20)
        self.assertEqual(got['gi.egd'][:2], ('performed', 'second part of duodenum'))
        self.assertNotIn(got['gi.colonoscopy'][0], ('performed', 'incomplete'))

    def test_the_summary_label_never_opens_in_a_plan(self):
        for label in ('Procedure summary', 'Procedure summary:'):
            with self.subTest(label=label):
                text = TABLE.format(heading='Plan\nRepeat in 3 years.\n' + label + '\n', table=SUMMARY,
                                    after='Signed electronically.')
                kinds = [s.kind for s in sections.layout(text).sections]
                self.assertNotIn('procedure', kinds[kinds.index('plan'):])

    def test_a_status_column_still_denies(self):
        text = TABLE.format(heading='Procedure summary\n',
                            table='Examination | Performed | Furthest point reached\n'
                                  'Upper endoscopy (EGD) | Yes | Second portion of the duodenum\nColonoscopy | No | -',
                            after='Plan\nColonoscopy not done today (inadequate preparation); rebook.')
        self.assertNotIn(status(text, 'gi.colonoscopy', DAY20), ('performed', 'incomplete'))
        self.assertEqual(extent(text, 'gi.egd', DAY20), 'second part of duodenum')
        alone = TABLE.format(heading='Procedure summary\n',
                             table='Examination | Performed | Furthest point reached\n'
                                   'Upper endoscopy (EGD) | Yes | Second portion of the duodenum\nColonoscopy | No | -',
                             after='Impression\nSee above.')  # the table's own "No" is the only denial
        self.assertNotIn(status(alone, 'gi.colonoscopy', DAY20), ('performed', 'incomplete'))

    def test_a_date_or_comment_cell_still_speaks_for_its_row(self):
        planned = TABLE.format(heading='Procedure summary\n',
                               table='Examination | Planned date | Indication\nColonoscopy | 2026-11-12 | Anemia',
                               after='Plan\nBooked for 2026-11-12.')
        self.assertNotIn(status(planned, 'gi.colonoscopy', DAY20), ('performed', 'incomplete'))
        cancelled = TABLE.format(heading='Procedure summary\n',
                                 table='Examination | Instrument | Comments\nColonoscopy | Adult colonoscope | Cancelled '
                                       'before insertion: inadequate preparation', after='Plan\nRebook.')
        self.assertIn(status(cancelled, 'gi.colonoscopy', DAY20), ('cancelled', 'negated'))

    def test_a_prior_procedures_table_is_history(self):
        text = SYNTHETIC + ('Lakeshore Endoscopy (fictional)\nColonoscopy Report\nDate of service: 2026-10-21\n'
                            'Indication\nSurveillance after adenomas.\nPrior procedures\nProcedure | Date | Result\n'
                            'Colonoscopy | 2019-05-02 | Two tubular adenomas, both removed\n'
                            'Colonoscopy | 2016-03-11 | Normal to the cecum\nProcedures performed: Colonoscopy\nFindings\n'
                            'The colonoscope was advanced to the cecum. A 4 mm sigmoid polyp was removed with a cold snare.\n')
        self.assertEqual(reading(text, date(2026, 10, 21))['gi.colonoscopy'][:2], ('performed', 'cecum'))


# --- R6, R7 and N1 ------------------------------------------------------------------------------------------------------

UPPER = SYNTHETIC + """Quillan Bend Surgical Center (fictional)
Upper Endoscopy Report
Date of service: 2026-10-07
Indications
Early satiety and vomiting.
{heading}
{body}
Impression
Gastric outlet obstruction.
"""
NOREACH = ('A large amount of retained food was present. The pyloric channel was narrowed by a clean-based ulcer and the '
           'gastroscope could not be passed through it; the duodenum was not examined.')


class UpperTests(unittest.TestCase):
    """R6, R7 and N1."""

    def test_composite_positive_headings(self):
        for heading in ('Procedure and findings', 'Procedure/Findings', 'Technique and findings', 'Procedure & findings',
                        'Findings, procedure'):
            with self.subTest(heading=heading):
                text = UPPER.format(heading=heading, body='The gastroscope was advanced into the stomach. ' + NOREACH)
                self.assertEqual(extent(text, 'gi.egd', UPPER_DAY), 'incomplete: stomach')

    def test_a_composite_heading_with_another_part_is_not_one(self):
        self.assertEqual(sections._composite_kind('procedure and plan'), None)
        self.assertEqual(sections._composite_kind('findings and procedure'), 'findings')
        self.assertEqual(sections._composite_kind('procedure'), None)  # a single part is HEADINGS' own

    def test_the_pyloric_outlet_is_the_stomach(self):
        for value in ('pyloric channel', 'pylorus', 'gastric antrum', 'prepyloric antrum', 'pyloric canal',
                      'gastric outlet'):
            with self.subTest(value=value):
                text = UPPER.format(heading='Findings', body=NOREACH + f'\nFurthest extent: {value}.')
                self.assertEqual(extent(text, 'gi.egd', UPPER_DAY), 'incomplete: stomach')

    def test_not_attempted_denies_the_act_across_its_object(self):
        for sentence in ('Balloon dilation of the channel was not attempted because the ulcer is active.',
                         'Dilation across the narrowed pyloric channel was not performed.'):
            with self.subTest(sentence=sentence):
                text = UPPER.format(heading='Findings', body='The gastroscope was advanced into the stomach. ' + NOREACH
                                    + ' ' + sentence)
                self.assertNotIn('dilation', reading(text, UPPER_DAY)['gi.egd'][2] or '')

    def test_a_denial_inside_a_relative_clause_never_reaches_the_act(self):
        for sentence in ('Biopsy of the polyp that was not removed was performed.',
                         'Biopsy at the site where clips were not placed.'):
            with self.subTest(sentence=sentence):
                text = COLON.format(body='The colonoscope was advanced to the cecum. ' + sentence, impression='See above.')
                self.assertEqual(reading(text, DAY)['gi.colonoscopy'][2], 'biopsy')
        text = COLON.format(body='The colonoscope was advanced to the cecum. Biopsies of the cecum were not obtained.',
                            impression='See above.')
        self.assertIsNone(reading(text, DAY)['gi.colonoscopy'][2])


# --- R9: labels in a reporting service part --------------------------------------------------------------------------------

BIDI = SYNTHETIC + """Northgate Endoscopy (fictional)
Bidirectional Endoscopy Report
Date of procedure: 2026-10-20
Procedures: Esophagogastroduodenoscopy with biopsies; colonoscopy.
Indications
Iron deficiency anemia, referred for upper and lower endoscopic evaluation.
Upper Endoscopy
The gastroscope was introduced without difficulty. {egd_label}: second portion of the duodenum. Cold forceps biopsies
were taken from the duodenum.
Colonoscopy
The colonoscope was introduced and advanced under direct vision. {colon_label}: cecum, confirmed by the appendiceal
orifice. No polyps.
Impression
See above.
"""


class ServicePartLabelTests(unittest.TestCase):
    """R9: a label in a reporting service part reads as an addendum's would."""

    def test_labels_in_service_parts(self):
        for label in ('Extent', 'Deepest point reached'):
            with self.subTest(label=label):
                text = BIDI.format(egd_label=label, colon_label=label)
                got = reading(text, DAY20)
                self.assertEqual(got['gi.egd'][1], 'second part of duodenum')
                self.assertEqual(got['gi.colonoscopy'][1], 'cecum')
                parts = sections.layout(text).reporting_parts
                self.assertEqual(len(parts), 2)


# --- cost -------------------------------------------------------------------------------------------------------------------

class CostTests(unittest.TestCase):
    """The new patterns and loops are linear (stage limits: analyze 60 s)."""

    def test_a_label_reads_a_long_blank_run_once(self):
        # read with plain runs, one label word before a long run of blanks was tried at every split of the run: at
        # 90377ec6f413 "Depth of insertion", 80,000 blanks and "30 cm" routed in 69 s
        for label in ('Depth of insertion', 'Extent', 'Reached'):
            text = label + ' ' * 40000 + 'x'
            with self.subTest(label=label):
                start = time.process_time()
                self.assertIsNone(cues.EXTENT_CM.search(text))
                self.assertIsNone(cues.EXTENT_LABEL_BEFORE.search(text))
                self.assertLess(time.process_time() - start, 2.0)  # about 0.01 s; with plain runs about 17 s each

    def test_a_summary_reads_its_reach_once(self):
        # each summary table's reach for another occasion ends at the next table's header: n tables back to back, with no
        # heading between them, read each line once (read to the next heading, they read n * n / 2 lines)
        calls, original = [], sections._names_another_occasion

        def counting(*args):
            calls.append(args[1])
            return original(*args)

        block = ('Procedure summary\nExamination | Instrument | Furthest point reached\n'
                 'Colonoscopy | Adult colonoscope | Cecum\n')
        text = TABLE.format(heading='', table=block * 200, after='Impression\nSee above.')
        with mock.patch.object(sections, '_names_another_occasion', counting):
            sections.layout.cache_clear()
            sections.layout(text)
        sections.layout.cache_clear()
        self.assertGreaterEqual(len(calls), 200)
        self.assertLessEqual(len(calls), 2 * 200)

    def test_a_cells_opening_is_read_once(self):
        # however many landmarks one extent cell holds, its opening word is found once (detect._extent_column)
        calls, original = [], detect._CELL_WORD

        class Counting:
            def finditer(self, *args):
                calls.append(args[1:])
                return original.finditer(*args)

        cell = 'the cecum ' + 'and the cecum ' * 300
        text = TABLE.format(heading='Procedure summary\n',
                            table=f'Examination | Instrument | Furthest point reached\nColonoscopy | Scope | {cell}',
                            after='Impression\nSee above.')
        with mock.patch.object(detect, '_CELL_WORD', Counting()):
            detect._analysis.cache_clear()
            route(text, DAY20)
        detect._analysis.cache_clear()
        self.assertEqual(len(calls), len(set(calls)))
        self.assertLessEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
