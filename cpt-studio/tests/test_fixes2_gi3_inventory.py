"""GI round 3, fix round 2, owner "inventory" (session 7c8d38da): the second refutation's inventory findings.

The second refutation of the integrated candidate (b6997c39d) found the documented-service inventory reading these shapes
wrong by the source, most of them in fix round 1's own repairs. Each is fixed by a general rule in studio/gi/services.py
or studio/validation/reconcile.py ("gi3 fix round 2 (<finding>)") that follows interpretation 51(e) - an act read from
a table cell, a relative clause or a summary needs its own affirmation, and an uncertain reading takes the safe
outcome - and adds no list that exempts anything from asking or holding (51(f)). Each test holds the reviewer's own
input (tests/fixtures/gi3/fix2_inventory, synthetic) and shapes of this owner's own beside it (another heading or
layout, a paraphrase, another section, a table, a PDF-style wrap) to the source-correct output, beside a control:

- INV2-1: a relative clause whose head is the act itself ("Polypectomy, which was not performed ...") is the act's own;
  its denial stands unless the act states its own predicate outside the relative clause.
- INV2-2: an act a table cell names under a negation of its own ("Yes, cold snare (no biopsies)") is denied there and
  never stated done; the column's own act named so is in doubt.
- INV2-3: a time another cell of a row states ("Within 8 weeks", "Next month", "Planned") holds the row's acts.
- INV2-4: a plan or history section joined to another kind ("Impression and plan"), a procedure-summary heading inside
  a plan section, and a date under a column of another occurrence hold a table's acts, never exclude them.
- INV2-5: a site written right before another act's noun is that act's; an exchange's duct system is the one its own
  noun phrase names.
- INV2-6: the heading lines above a table are read past one caption line; a time read beyond the first line holds.
- INV2-7: an aside naming a point's own site ("biopsies (gastric antrum)"), a service's own extent ("colonoscopy to the
  cecum") and the one service named before an act in its segment bind a procedure line's acts.
- INV2-8: an act's technique is never a word inside another act's mention ("fine-needle biopsy and gastric biopsies").
- INV2-9: a table heading's or label's negation doubts only what it governs ("no complications" doubts nothing), and a
  later-time word restating the document's own report title ("Repeat colonoscopy") names today's examination.
- INV2-10: a passive denial before an act ("Hemostasis was not required post-polypectomy") is its subject's, and a
  denial of another occurrence its own words name ("Repeat dilation was not needed") is no denial of today's act.
- INV2-11: an open-class word between a size and a lesion noun needs a lead ("a 25 mm firm mass"), so "at
  approximately 32 cm linear erosions" is no 32 cm lesion.
- INV2-12: a lesion named as an act's object keeps its descriptive words ("of an additional 6 mm polyp").
- rev2-scope-11: an evaluation statement a remote modality leads or carries is no office visit for the inventory.

Every document is synthetic. No network, no database.
"""
import time
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation import reconcile
from studio.validation.engine import assess

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'fix2_inventory'
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nPatient: Wren Fictional\n' \
       'Date of service: 2026-10-16\n'
NOT_READY = ('needs_clarification', 'excluded')


def fixture(name: str) -> str:
    return (FIXTURES / f'{name}.txt').read_text(encoding='utf-8')


def day_of(text: str):
    fact = gi_context.extract_context(text)['service_date']
    return date.fromisoformat(fact.value) if fact.value and fact.origin in ('document', 'user') else None


def read(text: str):
    """The inventory as the assess stage reads it: the context's service date, routing, then the inventory."""
    day = day_of(text)
    return services.build(text, service_date=day, routing=detect.route(text, day),
                          context_facts=gi_context.extract_context(text))


def acts(inv, family, kind=None, statuses=None):
    return [a for s in inv.services if s.family == family for a in s.acts
            if (kind is None or a.kind == kind) and (statuses is None or a.status in statuses)]


def described(inv, family):
    return [reconcile.describe_act(s, a) for s in inv.services if s.family == family for a in s.acts
            if a.status == 'performed']


def unresolved_kinds(inv, codes):
    unresolved, bundled, _ = reconcile.reconcile(inv, codes, procedure_day=True)
    return [(u.family, u.act) for u in unresolved], [b.act for b in bundled]


def result_of(text: str, picks):
    """The engine's result for provider-selected (code, quote) picks against an empty reference."""
    codes = []
    for index, (code, quote) in enumerate(picks):
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),), index=index))
    day = day_of(text)
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def statuses(text: str, picks) -> dict:
    return {p.code: p.status for p in result_of(text, picks).proposals}


def status(text: str, code: str, quote: str) -> str:
    return statuses(text, [(code, quote)])[code]


def colo(findings: str, after: str = '', title: str = 'Colonoscopy report') -> str:
    return HEAD + title + '\nFindings: The colonoscope was advanced to the cecum. ' + findings + '\n' + after


def egd(findings: str, after: str = '', title: str = 'Upper endoscopy report') -> str:
    return (HEAD + title + '\nFindings: The gastroscope was advanced to the second portion of the duodenum. ' + findings
            + '\n' + after)


class RelativeClauseHeadTests(SimpleTestCase):
    """INV2-1: a relative clause whose head noun is the act itself is the act's own clause."""

    def test_the_reviewers_act_headed_relative_clauses_deny_the_act(self):
        for name, family, kind, code, quote in (
                ('a31-act-head-which-not', 'gi.colonoscopy', 'snare', '45385',
                 'A 6 mm sessile polyp was seen in the sigmoid colon.'),
                ('a33-biopsies-which-were-not', 'gi.colonoscopy', 'biopsy', '45380',
                 'The colonoscope was advanced to the cecum.')):
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertFalse(acts(inv, family, kind, ('performed',)))
                self.assertTrue(acts(inv, family, kind, ('negated',)))
                self.assertIn(status(text, code, quote), NOT_READY)

    def test_own_shapes_of_an_act_headed_relative_clause(self):
        """Another verb and tense, an active relative clause, a PDF-style line wrap, an upper endoscopy, a complex noun
        phrase with no predicate of its own: never ready."""
        for findings, code, quote, maker in (
                ('A 7 mm polyp was seen in the rectum. Biopsy, which was not done because of anticoagulation, is '
                 'planned.', '45380', 'A 7 mm polyp was seen in the rectum.', colo),
                ('A 7 mm polyp was seen in the rectum. Cold snare polypectomy, which we did not perform today, will be '
                 'scheduled.', '45385', 'A 7 mm polyp was seen in the rectum.', colo),
                ('A 7 mm polyp was seen in the rectum. Polypectomy, which was not\nperformed because of apixaban, will be '
                 'done later.', '45385', 'A 7 mm polyp was seen in the rectum.', colo),
                ('A Schatzki ring was seen. Dilation, which was not performed, is recommended if dysphagia persists.',
                 '43249', 'A Schatzki ring was seen.', egd),
                ('A 7 mm polyp was seen in the rectum. Biopsies of the polyp, which were not taken because of bleeding, '
                 'will be repeated.', '45380', 'A 7 mm polyp was seen in the rectum.', colo),
                ('Biopsies, which were not taken because of bleeding, are planned for the next examination.', '45380',
                 'The colonoscope was advanced to the cecum.', colo)):
            with self.subTest(findings):
                self.assertIn(status(maker(findings), code, quote), NOT_READY)
        # another predicate's clause, coordinated before the act, is no predicate of the act's own
        for findings, code, quote, maker in (
                ('A 7 mm polyp was removed with a cold snare and biopsies, which were not taken because of bleeding, are '
                 'planned.', '45380', 'A 7 mm polyp was removed', colo),
                ('The gastroscope was passed into the stomach, and dilation, which was not performed, is recommended.',
                 '43249', 'The gastroscope was passed', egd)):
            with self.subTest(findings):
                self.assertIn(status(maker(findings), code, quote), NOT_READY)

    def test_another_head_nouns_relative_clause_never_denies_the_act(self):
        """Controls: the reviewer's a14 and a11, and the act's own predicate before the relative pronoun, before the act
        with nothing between, or right after the relative clause."""
        for name in ('a14-that-was-not-ctrl', 'a11-which-could-not'):
            with self.subTest(name):
                self.assertEqual(status(fixture(name), '45380', 'Cold forceps biopsies were taken'), 'ready')
        for findings, code, quote, maker in (
                ('Biopsies were obtained from the gastric ulcer, which was not removed.', '43239', 'Biopsies were obtained',
                 egd),
                ('Biopsy of the 30 mm mass that could not be removed was performed with cold forceps.', '45380',
                 'Biopsy of the 30 mm mass', colo),
                ('We took biopsies from the 15 mm polyp that was not removed.', '45380', 'We took biopsies', colo)):
            with self.subTest(findings):
                self.assertEqual(status(maker(findings), code, quote), 'ready')
        # fix round 1's EXT-2 input: the instrument's own mention ("cold forceps") takes the act's predicate before it
        inv = read((FIXTURES.parent / 'fix1_inventory' / 'rel-r2.txt').read_text(encoding='utf-8'))
        self.assertFalse([a for s in inv.services for a in s.acts if a.kind == 'biopsy' and a.status == 'negated'])


class CellDenialTests(SimpleTestCase):
    """INV2-2: an act a table cell names under a negation of its own is denied there, never stated done."""

    CASES = (('p01-polypectomy-no-biopsies', 'gi.colonoscopy', 'biopsy', '45385', 'removed with a cold snare', '45380'),
             ('p05-polypectomy-without-biopsy', 'gi.colonoscopy', 'biopsy', '45385', 'removed with a cold snare', '45380'),
             ('g03-cell-without-snare', 'gi.colonoscopy', 'snare', '45380', 'Random colon biopsies were taken with cold forceps',
              '45385'),
             ('q01-egd-dilation-no-biopsies', 'gi.egd', 'biopsy', '43249', 'dilated with an 18 mm through-the-scope balloon',
              '43239'))

    def test_the_reviewers_cells_deny_what_they_name(self):
        for name, family, denied, own_code, own_quote, denied_code in self.CASES:
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertFalse(acts(inv, family, denied, ('performed',)))
                self.assertEqual(inv.conflicts, ())
                row = next(line for line in text.splitlines() if ' | ' in line and 'Yes' in line)
                got = statuses(text, [(own_code, own_quote), (denied_code, row[:30])])
                self.assertEqual(got[own_code], 'ready')
                self.assertIn(got[denied_code], NOT_READY)
                self.assertEqual(unresolved_kinds(inv, [(own_code, family)])[0], [])

    def test_a_cells_denial_beside_the_prose_denial_is_no_conflict(self):
        inv = read(fixture('p02-polypectomy-no-biopsies-taken'))
        self.assertEqual(inv.conflicts, ())
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))

    def test_own_shapes_of_a_cells_denial(self):
        """A biopsy column denying a polypectomy, a spaced dash before a post-posed "not", a dash after "Yes", and an
        upper endoscopy's biopsy column denying a dilation."""
        table = 'Procedure summary\nExamination | Instrument | Furthest point reached | {col}\nColonoscopy | Adult colonoscope | Cecum | {cell}\n'
        for col, cell, body, kind, code_quote in (
                ('Biopsy', 'Yes, cold forceps; no polypectomy', 'Random biopsies were taken with cold forceps.', 'snare',
                 ('45385', 'Colonoscopy | Adult colonoscope')),
                ('Polypectomy', 'Yes, hot snare - biopsies not obtained',
                 'A 9 mm polyp in the rectum was removed with a hot snare.', 'biopsy', ('45380', 'Colonoscopy | Adult colonoscope')),
                ('Tissue sampled', 'Yes - snare only, no forceps', 'A 9 mm polyp in the rectum was removed with a cold snare.',
                 'biopsy', ('45380', 'Colonoscopy | Adult colonoscope'))):
            with self.subTest(cell):
                text = (HEAD + 'Colonoscopy report\n' + table.format(col=col, cell=cell)
                        + 'Findings: The colonoscope was advanced to the cecum. ' + body + '\n')
                inv = read(text)
                self.assertFalse(acts(inv, 'gi.colonoscopy', kind, ('performed',)))
                self.assertIn(status(text, *code_quote), NOT_READY)
                if col == 'Polypectomy':
                    # the cell's own undenied segment states its column's act: read performed (the summary row's act
                    # then merges with the body's polypectomy, the same act), never held
                    self.assertEqual(services._cell_acts(cell, 0, len(cell)), (('snare',), frozenset({'biopsy'})))
                    self.assertFalse(acts(inv, 'gi.colonoscopy', 'snare', ('uncertain',)))
                    self.assertEqual(status(text, '45385', 'removed with a hot snare'), 'ready')
        text = (HEAD + 'Upper endoscopy report\nProcedure summary\nExamination | Furthest point reached | Biopsy\n'
                'Upper endoscopy | Second portion of the duodenum | Yes, without dilation\nFindings: The gastroscope was '
                'advanced to the second portion of the duodenum. Gastric biopsies were taken.\n')
        self.assertFalse(acts(read(text), 'gi.egd', 'dilation', ('performed',)))
        self.assertEqual(statuses(text, [('43239', 'Gastric biopsies were taken'), ('43249', 'Upper endoscopy | Second')]),
                         {'43239': 'ready', '43249': 'needs_clarification'})
        cells = services._cell_acts('Yes, cold forceps without polypectomy', 0, 37)
        self.assertEqual(cells, (('biopsy',), frozenset({'snare'})))

    def test_a_cell_naming_its_acts_undenied_still_states_them(self):
        """Controls: the reviewer's p06 and g04, and a cell naming two acts with no negation."""
        self.assertEqual(status(fixture('p06-ctrl'), '45385', 'removed with a cold snare'), 'ready')
        self.assertEqual(status(fixture('g04-ctrl'), '45380', 'Random colon biopsies were taken with cold forceps'),
                         'ready')
        self.assertEqual(services._cell_acts('Yes, cold snare and cold forceps', 0, 32),
                         (('snare', 'biopsy'), frozenset()))


class RowTimeTests(SimpleTestCase):
    """INV2-3: a time another cell of a row states is the row's own time: it holds the row's acts."""

    def test_the_reviewers_scheduled_rows_are_never_todays(self):
        for name in ('i11-scheduling', 'i12-booked-procedures', 'i13-referral-for-emr', 'i16-disposition',
                     'i02-dedicated-session'):
            with self.subTest(name):
                text = fixture(name)
                self.assertFalse(acts(read(text), 'gi.colonoscopy', 'emr', ('performed',)))
                row = 'Colonoscopy | Within 8 weeks | Yes, EMR | Yes'
                for code, got in statuses(text, [('45390', row), ('45381', row)]).items():
                    self.assertIn(got, NOT_READY, code)

    def test_own_shapes_of_a_rows_own_time(self):
        """Other headings and time columns: a span, a relative time, a time from now, a status cell's plan word."""
        for heading, column, cell in (('Arranged sessions', 'Interval', 'In 6 weeks'), ('Work list', 'When', 'Next month'),
                                      ('Disposition', 'Timing', '3 weeks from now'), ('Disposition', 'Status', 'Planned')):
            with self.subTest(cell):
                text = (HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. A 20 mm flat '
                        'lesion in the ascending colon was seen; it was left for a dedicated session.\n' + heading
                        + f'\nExamination | {column} | Polypectomy\nColonoscopy | {cell} | Yes, EMR\n')
                emr = [a.status for a in acts(read(text), 'gi.colonoscopy', 'emr')]
                self.assertIn('uncertain', emr)  # the table's reading; the row line's prose may read it planned too
                self.assertNotIn('performed', emr)
                self.assertIn(status(text, '45390', f'Colonoscopy | {cell} | Yes, EMR'), NOT_READY)

    def test_todays_row_and_a_plan_sections_table(self):
        """Controls: a row timed today is today's; the reviewer's "Next steps" table stays planned (a plan section)."""
        text = (HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. A 20 mm flat lesion in the '
                'ascending colon was removed by EMR.\nProcedure summary\nExamination | Timing | Polypectomy\n'
                'Colonoscopy | Today | Yes, EMR\n')
        self.assertEqual(status(text, '45390', 'Colonoscopy | Today | Yes, EMR'), 'ready')
        self.assertEqual([a.status for a in acts(read(fixture('i01-next-steps')), 'gi.colonoscopy', 'emr')], ['planned'])


class SectionTimeTests(SimpleTestCase):
    """INV2-4: a section joined to another kind, a summary heading inside a plan, a column of another occurrence: held,
    never excluded."""

    QUOTE = 'Yes, random colon biopsies with cold forceps'

    def test_the_reviewers_summary_tables_are_never_excluded(self):
        for name in ('f01-impression-and-plan-table', 'f02-summary-after-plan', 'c01-prior-exam-column-year'):
            with self.subTest(name):
                text = fixture(name)
                self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'biopsy')], ['uncertain'])
                self.assertEqual(status(text, '45380', self.QUOTE), 'needs_clarification')

    def test_own_shapes_of_a_sections_doubtful_reach(self):
        """"Assessment and plan", a summary heading after a plan's prose, a "Previous colonoscopy" column, and
        "Impression/Plan": held, never excluded."""
        table = ('Examination | Furthest point reached | Tissue sampled\nColonoscopy | Cecum | Yes, random biopsies with '
                 'cold forceps\n')
        body = HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. Normal mucosa.\n'
        for text in (body + 'Assessment and plan\n' + table + 'Await pathology.\n',
                     body + 'Plan\nAwait pathology.\nProcedure summary\n' + table,
                     body + 'Procedure summary\nExamination | Furthest point reached | Tissue sampled | Previous '
                            'colonoscopy\nColonoscopy | Cecum | Yes, random biopsies with cold forceps | 2018, two adenomas\n',
                     body + 'Impression/Plan\n' + table):
            with self.subTest(text[-120:]):
                self.assertEqual(status(text, '45380', 'Yes, random biopsies with cold forceps'), 'needs_clarification')

    def test_todays_summary_and_a_dated_plan_row(self):
        """Controls: the reviewer's f03 (the summary before the plan) is today's; a plan row dated later stays planned."""
        self.assertEqual(status(fixture('f03-ctrl-summary-before-plan'), '45380', self.QUOTE), 'ready')
        text = (HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. Normal mucosa.\nPlan\n'
                'Examination | Due | Tissue sampled\nColonoscopy | March 2029 | Yes\n')
        self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'biopsy')], ['planned'])

    def test_a_section_labels_own_kind(self):
        layout = services._sections.Section
        for label, kind, when in (('plan', 'plan', 'planned'), ('next steps', 'plan', 'planned'),
                                  ('recommendations and plan', 'plan', 'planned'), ('impression and plan', 'plan', 'uncertain'),
                                  ('assessment/plan', 'plan', 'uncertain'), ('past medical and surgical history', 'history',
                                                                            'historical'), ('findings', 'findings', '')):
            with self.subTest(label):
                self.assertEqual(services._section_time(layout(kind, label, None, 0, 1)), when)

    def test_only_a_column_that_times_the_row_dates_it(self):
        """A date in a column that does not time the row ("Pathology expected | 2026-10-23", "Report sent |
        2026-10-20") is that column's: held, never excluded as planned (the installed revision excluded c04). Control: a
        "Date" column still dates its row."""
        self.assertEqual(status(fixture('c04-pathology-due-column'), '45380', self.QUOTE), 'needs_clarification')
        body = HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. Normal mucosa.\nProcedure summary\n'
        text = body + 'Examination | Furthest point reached | Tissue sampled | Report sent\nColonoscopy | Cecum | Yes, random ' \
                      'biopsies with cold forceps | 2026-10-20\n'
        self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'biopsy')], ['uncertain'])
        text = body.replace('Procedure summary', 'Examination record') + 'Examination | Date | Tissue sampled\n' \
                                                                        'Colonoscopy | 2019-03-02 | Yes\n'
        self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'biopsy')], ['historical'])
        # a time column that names another occurrence dates that occurrence, never today's row: held
        text = body + 'Examination | Tissue sampled | Date of last colonoscopy\nColonoscopy | Yes, random biopsies with cold ' \
                      'forceps | 2019-03-02\n'
        self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'biopsy')], ['uncertain'])


class ExchangeNounPhraseTests(SimpleTestCase):
    """INV2-5: a site before another act's noun is that act's; an exchange's duct system is its own noun phrase's."""

    def test_the_reviewers_exchanges_keep_their_own_biliary_parts(self):
        text = fixture('y3-removal-site-procline-pd-stent')
        inv = read(text)
        self.assertFalse([a for a in acts(inv, 'gi.ercp', 'stent_exchange') if 'pancreatic duct' in a.anatomy])
        self.assertEqual(statuses(text, [('43276', 'Biliary stent exchanged'),
                                         ('43275', 'The existing plastic stent was removed from the common bile duct with a '
                                                   'snare.'),
                                         ('43274', 'A 5 French pancreatic duct stent was also placed in the pancreatic duct.')]),
                         {'43276': 'ready', '43275': 'needs_clarification', '43274': 'ready'})
        text = fixture('y2-placement-site-procline-duodenal-biopsies')
        self.assertEqual(reconcile.match('43274', read(text), 'gi.ercp').reason, reconcile.EXCHANGE_PART)
        self.assertEqual(statuses(text, [('43276', 'Biliary stent exchanged'),
                                         ('43274', 'A new 10 French by 9 cm plastic stent was placed in the common bile '
                                                   'duct across the stricture')]),
                         {'43276': 'ready', '43274': 'needs_clarification'})

    def test_the_pancreatic_duct_stent_beside_the_exchange_is_its_own(self):
        for name in ('x1-procline-exchange-then-pd-stent', 'y3-removal-site-procline-pd-stent'):
            with self.subTest(name):
                inv = read(fixture(name))
                _, bundled = unresolved_kinds(inv, [('43276', 'gi.ercp')])
                stents = [a for a in acts(inv, 'gi.ercp', 'stent', ('performed',)) if 'pancreatic duct' in a.anatomy]
                self.assertTrue(stents)
                service = reconcile.service_for(inv, 'gi.ercp')
                self.assertTrue(all(reconcile.exchange_of(service, a) is None for a in stents))

    def test_own_shapes_of_an_exchanges_own_words(self):
        """A comma-listed procedure line, "Exchange of the biliary stent", and a pancreatic exchange beside a biliary
        placement."""
        ercp = (HEAD + 'ERCP procedure note\n{line}\nProcedure\nThe duodenoscope was advanced to the major papilla. The '
                'existing plastic stent was removed from the common bile duct with a snare. The bile duct was cannulated '
                'with a sphincterotome over a guidewire. A new 10 French plastic stent was placed in the common bile duct. '
                '{extra}\nImpression\n{imp}\n')
        text = ercp.format(line='Procedures: ERCP, biliary stent exchange, pancreatic duct stent placement.',
                           extra='A 5 French pancreatic duct stent was also placed in the pancreatic duct.',
                           imp='Biliary stent exchanged.')
        self.assertEqual(statuses(text, [('43275', 'The existing plastic stent was removed'),
                                         ('43274', 'A 5 French pancreatic duct stent')]),
                         {'43275': 'needs_clarification', '43274': 'ready'})
        text = ercp.format(line='Procedure: Exchange of the biliary stent and duodenal biopsies.',
                           extra='Biopsies of the second portion of the duodenum were taken.',
                           imp='Biliary stent exchanged; duodenal biopsies taken.')
        self.assertEqual(status(text, '43274', 'A new 10 French plastic stent was placed'), 'needs_clarification')
        text = (HEAD + 'ERCP procedure note\nProcedures: ERCP with pancreatic duct stent exchange and biliary stent '
                'placement.\nProcedure\nThe pancreatic duct was cannulated. The pancreatic duct stent was exchanged for a '
                'new 5 French stent. The bile duct was cannulated. A 10 French plastic stent was placed in the common bile '
                'duct for the stricture.\nImpression\nPancreatic duct stent exchanged; biliary stent placed.\n')
        self.assertEqual(status(text, '43274', 'A 10 French plastic stent was placed in the common bile duct'), 'ready')
        # another act's object on the procedure line is no site of the exchange's: its own biliary parts stay its parts
        for line, imp in (('Procedures: ERCP with stent exchange and biopsies of the duodenum.', 'Stent exchanged.'),
                          ('Procedures: ERCP with stent exchange and placement of a stent in the pancreatic duct.',
                           'Stent exchanged.')):
            with self.subTest(line):
                text = ercp.format(line=line, extra='Biopsies of the second portion of the duodenum were taken.', imp=imp)
                self.assertFalse([a for a in acts(read(text), 'gi.ercp', 'stent_exchange') if a.anatomy])
                self.assertEqual(statuses(text, [('43275', 'The existing plastic stent was removed'),
                                                 ('43274', 'A new 10 French plastic stent was placed')]),
                                 {'43275': 'needs_clarification', '43274': 'needs_clarification'})

    def test_an_exchanges_noun_phrase(self):
        for passage, systems in (('Biliary stent exchanged: one plastic stent removed.', {'biliary'}),
                                 ('Procedures: ERCP with biliary stent exchange and pancreatic duct stent placement.',
                                  {'biliary'}),
                                 ('Procedures: ERCP with pancreatic duct stent placement and biliary stent exchange.',
                                  {'biliary'}),
                                 ('We exchanged the pancreatic stent.', {'pancreas'}),
                                 ('Benign common bile duct stricture. Stent exchanged.', set())):
            with self.subTest(passage):
                self.assertEqual(reconcile._named_systems(passage), systems)

    def test_a_site_before_its_own_noun_and_one_act_named_twice(self):
        """Controls: "duodenal biopsies" keeps its site; a stone extraction named twice shares its site; a finding's
        participle takes no site ("a common bile duct dilated to 11 mm contained two stones")."""
        inv = read(egd('Duodenal biopsies were obtained with cold forceps.'))
        self.assertEqual({a.anatomy for a in acts(inv, 'gi.egd', 'biopsy', ('performed',))}, {('duodenum',)})
        text = (HEAD + 'ERCP procedure note\nFindings: A common bile duct dilated to 11 mm contained two stones. A biliary '
                'sphincterotomy was performed and the stones were removed with an extraction balloon.\n')
        self.assertIn(('common bile duct',), [a.anatomy for a in acts(read(text), 'gi.ercp', 'stone_extraction')])


class HeadingLinesTests(SimpleTestCase):
    """INV2-6: the heading lines above a table are read past one caption line; a time beyond the first line holds."""

    def test_the_reviewers_captioned_prior_tables(self):
        for name in ('h01-prior-reviewed-caption', 'h02-prior-reviewed-sentence'):
            with self.subTest(name):
                text = fixture(name)
                # a heading beyond the first line cannot be placed for certain: held, never dated
                self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'snare')], ['uncertain'])
                self.assertIn(status(text, '45385', 'Yes, cold snare'), NOT_READY)
        self.assertEqual([a.status for a in acts(read(fixture('h03-ctrl-prior-reviewed')), 'gi.colonoscopy', 'snare')],
                         ['historical'])

    def test_own_shapes_of_a_captioned_table(self):
        table = 'Examination | Findings | Polypectomy\nColonoscopy | Two tubular adenomas | Yes, cold snare\n'
        for above in ('Previous colonoscopies\nFrom the outside endoscopy unit\n',
                      'Prior examinations\nSummary sent by the referring physician.\n'):
            with self.subTest(above):
                text = (HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. No polyps were '
                        'found.\n' + above + table + 'Impression\nNormal colonoscopy.\n')
                self.assertIn(status(text, '45385', 'Yes, cold snare'), NOT_READY)

    def test_a_procedure_summary_heading_stops_the_walk(self):
        """Control: today's procedure summary under a caption line is today's."""
        text = (HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. Two polyps were removed '
                'with a cold snare.\nProcedure summary\nToday\'s examination\nExamination | Findings | Polypectomy\n'
                'Colonoscopy | Two tubular adenomas | Yes, cold snare\n')
        self.assertEqual(status(text, '45385', 'Yes, cold snare'), 'ready')


class ProcedureLineItemTests(SimpleTestCase):
    """INV2-7: a procedure line's items: an aside naming a point's own site, a service's own extent, and the service
    named before an act."""

    def test_the_reviewers_procedure_lines(self):
        for name, picks, expected in (
                ('s01-parenthesized-sites', [('43239', 'EGD with'), ('45385', 'cold snare polypectomy')],
                 {'43239': 'ready', '45385': 'ready'}),
                ('s02-taken-from', [('43239', 'EGD with'), ('45385', 'cold snare polypectomy')],
                 {'43239': 'ready', '45385': 'ready'}),
                ('s03-dash-sites', [('43239', 'EGD with'), ('45385', 'cold snare polypectomy')],
                 {'43239': 'ready', '45385': 'ready'}),
                ('s11-egd-biopsies-colonoscopy-to-cecum',
                 [('43239', 'EGD with'), ('45385', 'cold snare polypectomy'), ('45380', 'EGD with')],
                 {'43239': 'ready', '45385': 'ready', '45380': 'needs_clarification'}),
                ('s12-egd-biopsies-colonoscopy-to-ti',
                 [('43239', 'EGD with'), ('45385', 'cold snare polypectomy'), ('45380', 'EGD with')],
                 {'43239': 'ready', '45385': 'ready', '45380': 'needs_clarification'})):
            with self.subTest(name):
                text = fixture(name)
                self.assertEqual(statuses(text, picks), expected)
                inv = read(text)
                self.assertFalse(acts(inv, 'gi.egd', 'snare'))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy'))
                self.assertFalse([a for a in acts(inv, 'gi.egd', 'biopsy') if a.region in services.LOWER])

    def test_own_shapes_of_a_procedure_lines_items(self):
        line = (HEAD + 'Endoscopy report\nDate of procedure: 2026-10-16\n{line}\nThe gastroscope was advanced to the '
                'second portion of the duodenum. The colonoscope was advanced to the cecum. One 5 mm sessile polyp in the '
                'sigmoid colon.\nMild gastritis; one sigmoid polyp.\n')
        for proc in ('Procedures: EGD with cold forceps biopsies (antrum), colonoscopy with hot snare polypectomy (rectum).',
                     'Procedures: EGD with biopsies and colonoscopy into the terminal ileum with cold snare polypectomy.',
                     'Procedures: Colonoscopy to the cecum with cold snare polypectomy and EGD with biopsies.'):
            with self.subTest(proc):
                text = line.format(line=proc)
                got = statuses(text, [('43239', 'EGD with'), ('45385', 'snare polypectomy'), ('45380', 'EGD with')])
                self.assertEqual(got, {'43239': 'ready', '45385': 'ready', '45380': 'needs_clarification'})

    def test_controls_and_the_comma_list_limit(self):
        """Controls: s05 and s13. Known limit: a bare comma joins a list as often as it sets off a site ("biopsies,
        gastric antrum, and colonoscopy with ..."): s04's snare keeps the antrum, as installed."""
        for name in ('s05-ctrl', 's13-egd-biopsies-colonoscopy-cecum-ctrl'):
            with self.subTest(name):
                self.assertEqual(status(fixture(name), '45385', 'cold snare polypectomy'), 'ready')
        text = fixture('s04-comma-site')
        self.assertEqual(statuses(text, [('43239', 'EGD with'), ('45385', 'cold snare polypectomy')]),
                         {'43239': 'ready', '45385': 'needs_clarification'})


class OtherMentionTechniqueTests(SimpleTestCase):
    """INV2-8: an act's technique is never a word inside another act's mention, unless that mention is its own
    instrument phrase."""

    def test_the_reviewers_gastric_biopsies_are_no_needle_sampling(self):
        text = fixture('u01-eus-procline-gastric-biopsies')
        inv = read(text)
        antral = [a for a in acts(inv, 'gi.eus', 'biopsy', ('performed',)) if 'gastric antrum' in a.anatomy]
        self.assertEqual([a.technique for a in antral], [''])
        result = result_of(text, [('43238', 'the tail mass was sampled from the gastric body')])
        unresolved = next(c for c in result.encounter_checks if c.id == 'services.unresolved')
        self.assertEqual(unresolved.status, 'warn')
        self.assertIn('gastric antrum', unresolved.detail)
        self.assertEqual(result.completeness.get('state'), 'incomplete')

    def test_own_shapes_of_another_mentions_technique(self):
        eus = (HEAD + 'Endoscopic ultrasound report\nProcedure: {line}\nFindings: The echoendoscope was advanced to the '
               'duodenum. A 20 mm hypoechoic mass in the pancreatic head was sampled with a 22-gauge needle. {body}\n'
               'Impression\nPancreatic head mass, sampled.\n')
        for line, body, site in (('EUS with fine-needle aspiration and duodenal biopsies.',
                                  'Biopsies of the duodenal bulb were taken for celiac disease.', 'duodenal bulb'),
                                 ('EUS with 22-gauge needle sampling and gastric biopsies.',
                                  'Gastric antral biopsies were taken for Helicobacter pylori.', 'gastric antrum')):
            with self.subTest(line):
                inv = read(eus.format(line=line, body=body))
                biopsies = [a for a in acts(inv, 'gi.eus', 'biopsy', ('performed',)) if site in a.anatomy]
                self.assertTrue(biopsies)
                self.assertFalse([a for a in biopsies if 'needle' in a.technique])
        text = (HEAD + 'Colonoscopy report\nProcedure: Colonoscopy with balloon sweep and biopsies.\n')
        self.assertEqual(services._technique(text, 0, len(text), near=text.index('biopsies'), kind='biopsy',
                                             mentions=services._acts_in(text, 0, len(text)),
                                             starts=[a for _, a, _ in services._acts_in(text, 0, len(text))],
                                             own_end=text.index('biopsies') + 8), '')

    def test_an_acts_own_instrument_phrase_keeps_its_technique(self):
        """Control: "the tail mass was sampled ... with a 22-gauge fork-tip biopsy needle" keeps the needle."""
        inv = read(fixture('u02-eus-ctrl-no-procline-biopsies'))
        self.assertTrue([a for a in acts(inv, 'gi.eus', 'biopsy', ('performed',)) if a.technique == 'needle'])

    def test_an_instruments_own_measure_keeps_it(self):
        """gi3 fix round 2 (INV2-8), the gate's detail reading: "removed by piecemeal endoscopic mucosal resection with a
        15 mm stiff snare" keeps its own snare (INSTRUMENT_LEAD reads the instrument's measure)."""
        inv = read(colo('In the mid ascending colon there was a 30 mm granular-type laterally spreading lesion. The '
                        'lesion was removed by piecemeal endoscopic mucosal resection with a 15 mm stiff snare in five '
                        'pieces.'))
        self.assertIn('snare', [a.technique for a in acts(inv, 'gi.colonoscopy', 'emr', ('performed',))])
        # ... and only an act's own: another act named between it and the phrase takes the instrument
        inv = read(HEAD + 'Esophageal motility report\nProcedure: Esophageal manometry, followed by esophageal dilation '
                   'with a 54 Fr Maloney bougie.\n')
        techniques = {a.kind: a.technique for s in inv.services for a in s.acts if a.kind in ('manometry', 'dilation')}
        self.assertEqual(techniques, {'manometry': '', 'dilation': 'guidewire'})

    def test_a_mention_of_the_acts_own_kind_is_the_same_act(self):
        """gi3 fix round 2 (INV2-8), the live replay's ho-10: "Biopsies: cold forceps biopsies were taken from the
        proximal esophagus ..." names one biopsy twice, and its cold forceps are its own."""
        inv = read(HEAD + 'Upper endoscopy report\nProcedure: EGD with through-the-scope balloon dilation and cold '
                   'forceps biopsies.\nFindings: The gastroscope was advanced to the second portion of the duodenum.\n'
                   'Biopsies: cold forceps biopsies were taken from the proximal esophagus at 25 cm and the mid '
                   'esophagus at 30 cm (container 1).\n')
        self.assertEqual([a.technique for a in acts(inv, 'gi.egd', 'biopsy', ('performed',))], ['cold forceps'])
        self.assertEqual([a.technique for a in acts(inv, 'gi.egd', 'dilation', ('performed',))], ['balloon'])
        for gap, own in (('with a 15 mm stiff ', True), ('with a 54 Fr Maloney ', True), ('using the 10 mm ', True),
                         ('via a 2.8 mm channel ', True), ('with ', True),
                         ('with biopsies of the ', False), ('and the ', False), ('with a 15 mm stiff long braided ', False)):
            with self.subTest(gap):
                self.assertEqual(services.INSTRUMENT_LEAD.search(gap) is not None, own)


class TableTodayWordsTests(SimpleTestCase):
    """INV2-9: a table heading's or label's negation doubts only what it governs; a later-time word restating the
    document's own report title names today's examination."""

    QUOTE = 'Yes, random colon biopsies with cold forceps'

    def test_the_reviewers_headings_and_labels_name_todays_examination(self):
        for name in ('d01-heading-no-complications', 'd02-heading-repeat-colonoscopy', 'd03-heading-follow-up-colonoscopy',
                     'e01-label-repeat', 'e02-label-no-sedation', 'd04-ctrl-heading'):
            with self.subTest(name):
                text = fixture(name)
                self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'biopsy')], ['performed'])
                self.assertEqual(status(text, '45380', self.QUOTE), 'ready')

    def test_own_shapes_of_todays_words(self):
        table = 'Examination | Furthest point reached | Tissue sampled\n{label} | Cecum | Yes, random biopsies with cold forceps\n'
        doc = HEAD + '{title}\nFindings: The colonoscope was advanced to the cecum. Scattered diverticula.\n{heading}\n' + \
            table + 'Impression\nDiverticulosis.\n'
        for title, heading, label in (('Colonoscopy report', 'Procedure summary (no adverse events)', 'Colonoscopy'),
                                      ('Colonoscopy report', 'Procedure summary', 'Colonoscopy (without sedation)'),
                                      ('Follow-up colonoscopy report', 'Follow-up colonoscopy -\nsummary', 'Colonoscopy')):
            with self.subTest(heading + label):
                text = doc.format(title=title, heading=heading, label=label)
                self.assertEqual(status(text, '45380', 'Yes, random biopsies with cold forceps'), 'ready')
        text = (HEAD + 'Repeat EGD report\nFindings: The gastroscope was advanced to the second portion of the duodenum. '
                'Gastritis.\nProcedure summary\nExamination | Furthest point reached | Tissue sampled\nRepeat EGD | Second '
                'portion of the duodenum | Yes, gastric biopsies\nImpression\nGastritis.\n')
        self.assertEqual(status(text, '43239', 'Yes, gastric biopsies'), 'ready')

    def test_a_negation_of_the_tables_own_thing_still_holds(self):
        """Controls: "Procedures not performed", "Colonoscopy (not done)" and a "Repeat colonoscopy summary" under a
        plain title (a later examination's, or today's: held) are never ready."""
        table = 'Examination | Furthest point reached | Tissue sampled\n{label} | Cecum | Yes, random biopsies with cold forceps\n'
        doc = HEAD + 'Colonoscopy report\nFindings: The colonoscope was advanced to the cecum. Scattered diverticula.\n' \
                     '{heading}\n' + table
        for heading, label in (('Procedures not performed', 'Colonoscopy'), ('Procedure summary', 'Colonoscopy (not done)'),
                               ('Repeat colonoscopy summary', 'Colonoscopy')):
            with self.subTest(heading + label):
                text = doc.format(heading=heading, label=label)
                self.assertIn(status(text, '45380', 'Yes, random biopsies with cold forceps'), NOT_READY)

    def test_the_table_time_reader(self):
        text = 'Procedure summary (no complications)|Colonoscopy (no)|Repeat colonoscopy summary|No colonoscopy'
        cut = [0, text.index('|'), text.index('|', text.index('|') + 1), text.rindex('|'), len(text)]
        spans = [(cut[0], cut[1]), (cut[1] + 1, cut[2]), (cut[2] + 1, cut[3]), (cut[3] + 1, cut[4])]
        day = date(2026, 10, 16)
        got = [services._table_time(text, a, b, day, (), []) for a, b in spans]
        self.assertEqual(got, ['', 'unknown', 'later', 'unknown'])
        a, b = spans[2]
        self.assertEqual(services._table_time(text, a, b, day, (), [], ('repeat colonoscopy report',)), '')
        self.assertEqual(services._table_time('Prior colonoscopy summary', 0, 25, day, (), [],
                                              ('prior colonoscopy review',)), 'earlier')
        for label, when in (('Colonoscopy (none performed)', 'unknown'), ('No biopsies done', 'unknown'),
                            ('Colonoscopy (no polyps found)', '')):
            with self.subTest(label):
                self.assertEqual(services._table_time(label, 0, len(label), day, (), []), when)


class PassiveDenialTests(SimpleTestCase):
    """INV2-10: a passive denial before an act is its subject's; a denial of another occurrence the act's own words name
    is no denial of today's act."""

    def test_the_reviewers_denials_of_another_subject(self):
        for name, code, quote, family in (
                ('a02-post-polypectomy-hemostasis', '45385', 'removed with a cold snare', 'gi.colonoscopy'),
                ('a22-clips-not-required-post', '45385', 'removed with a cold snare', 'gi.colonoscopy'),
                ('a25-hemostasis-not-required-at-completion', '45385', 'removed with a cold snare', 'gi.colonoscopy'),
                ('a06-hemostasis-not-required-post-space', '45385', 'removed with a cold snare', 'gi.colonoscopy'),
                ('a07-not-needed-upon', '45385', 'removed with a cold snare', 'gi.colonoscopy'),
                ('a23-egd-biopsies-not-taken-post-dilation', '43249', 'dilated with an 18 mm through-the-scope balloon',
                 'gi.egd'),
                ('a24-egd-not-needed-post-dilation', '43249', 'dilated with an 18 mm through-the-scope balloon', 'gi.egd')):
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertEqual(inv.conflicts, ())
                self.assertEqual(status(text, code, quote), 'ready')

    def test_own_shapes_of_another_subjects_denial(self):
        for findings, code, quote, maker in (
                ('A 6 mm polyp in the sigmoid colon was removed with a cold snare. Hemostasis was not required on '
                 'completion of the polypectomy.', '45385', 'removed with a cold snare', colo),
                ('A 6 mm polyp in the sigmoid colon was removed with a cold snare. Prophylactic clipping was not indicated '
                 'for this polypectomy.', '45385', 'removed with a cold snare', colo),
                ('A distal esophageal stricture was dilated with an 18 mm balloon. Biopsies were not needed given the '
                 'dilation.', '43249', 'dilated with an 18 mm balloon', egd),
                ('Antral biopsies were taken with cold forceps. Repeat biopsy was not required.', '43239',
                 'Antral biopsies were taken', egd)):
            with self.subTest(findings):
                text = maker(findings)
                self.assertEqual(read(text).conflicts, ())
                self.assertEqual(status(text, code, quote), 'ready')

    def test_the_acts_own_denial_still_denies_it(self):
        """Controls: a passive denial whose subject is the act, and an active one whose object it is."""
        text = colo('A 25 mm mass in the rectum was seen. Polypectomy was not attempted.')
        self.assertTrue(acts(read(text), 'gi.colonoscopy', 'snare', ('negated',)))
        self.assertIn(status(text, '45385', 'Polypectomy was not attempted'), NOT_READY)
        text = colo('The mucosa was normal. I did not take biopsies.')
        self.assertTrue(acts(read(text), 'gi.colonoscopy', 'biopsy', ('negated',)))
        self.assertEqual(services._denies_its_act('Hemostasis was not required post-polypectomy.', 10, 46, 36), False)
        self.assertEqual(services._denies_its_act('Hemostasis was not required post-polypectomy.', 0, 46, 0), True)

    def test_known_limit_a_participle_of_another_subject(self):
        """Known limit (as installed): "Clips were not placed post-polypectomy" reads the participle as the clause's act
        predicate, so the polypectomy is denied too and 45385 is asked as a conflict."""
        text = fixture('a03-clips-not-placed-post')
        self.assertTrue(read(text).conflicts)
        self.assertEqual(status(text, '45385', 'removed with a cold snare'), 'needs_clarification')


class PositionLeadTests(SimpleTestCase):
    """INV2-11: an open-class word between a size and a lesion noun needs a lead."""

    def test_the_reviewers_insertion_distances_are_no_sizes(self):
        for name in ('b01-at-approximately-32-cm', 'b02-at-approx-dot-32-cm', 'b03-from-30-to-32-cm',
                     'b04-at-32-and-34-cm', 'b06-ctrl-at-32-cm'):
            with self.subTest(name):
                inv = read(fixture(name))
                self.assertFalse([les for s in inv.services for les in s.lesions if les.size])
                self.assertIn('forceps biopsy (cold forceps) at the distal esophagus', described(inv, 'gi.egd'))

    def test_own_shapes_of_a_measured_position(self):
        for findings in ('In the mid esophagus around 28 cm longitudinal erosions were biopsied with cold forceps.',
                         'In the distal esophagus between 30 and 32 cm superficial ulcers were biopsied with cold forceps.',
                         'In the distal esophagus at roughly 35 cm patchy erosions were biopsied with cold forceps.'):
            with self.subTest(findings):
                inv = read(egd(findings))
                self.assertFalse([les for s in inv.services for les in s.lesions if les.size])

    def test_a_lead_keeps_a_lesions_own_words(self):
        """Controls: a lead (an article or a count) opens a lesion's size and its descriptive words."""
        for phrase, size, morph in (('a 25 mm firm, friable, ulcerated mass', '25 mm ', 'firm, friable, ulcerated '),
                                    ('Two 5 mm hyperplastic polyps', '5 mm ', 'hyperplastic '),
                                    ('6 mm sessile polyp', '6 mm ', 'sessile ')):
            with self.subTest(phrase):
                m = services.LESION.search(phrase)
                self.assertEqual((m.group('size'), m.group('morph')), (size, morph))
        self.assertEqual(services.LESION.search('at approximately 32 cm linear erosions').group('size'), None)

    def test_a_measure_that_opens_its_phrase_keeps_its_words(self):
        """gi3 fix round 2 (INV2-11), the gate's detail reading: a table cell that opens with the lesion's size ("L3 |
        Mid jejunum | 9 mm smooth submucosal-appearing nodule | Cold forceps biopsies x 3") keeps the nodule, and its
        biopsy is the nodule's - never one of the angioectasia the rows above name."""
        text = (HEAD + 'Small bowel enteroscopy report\nProcedure: Double-balloon enteroscopy, antegrade route.\n\n'
                'Lesion | Site | Description | Treatment | Specimen\n'
                'L1 | Proximal jejunum | 6 mm angioectasia, not bleeding | Argon plasma coagulation | -\n'
                'L2 | Proximal jejunum | 4 mm angioectasia, not bleeding | Argon plasma coagulation | -\n'
                'L3 | Mid jejunum | 9 mm smooth submucosal-appearing nodule | Cold forceps biopsies x 3 | Jar 1\n\n'
                'Impression\nJejunal angioectasias ablated; mid-jejunal nodule biopsied.\n')
        inv = read(text)
        service = reconcile.service_for(inv, 'gi.enteroscopy')
        lesion = {les.id: (les.size, les.morphology, les.noun) for les in service.lesions}
        self.assertIn(('9 mm', 'smooth submucosal-appearing', 'nodule'), lesion.values())
        self.assertEqual([lesion.get(a.lesion) for a in acts(inv, 'gi.enteroscopy', 'biopsy', ('performed',))],
                         [('9 mm', 'smooth submucosal-appearing', 'nodule')])
        for phrase, size in (('Findings: 25 mm firm friable mass', '25 mm '), ('Findings:\n8 mm smooth nodule', '8 mm '),
                             ('[x] 8 mm granular polyp', '8 mm '), ('\u2612 8 mm granular polyp', '8 mm '),
                             ('x\n- 8 mm granular polyp', '8 mm '), ('x\n12. 8 mm granular polyp', '8 mm '),
                             ('L3\tMid jejunum\t8 mm smooth nodule', '8 mm '), ('(8 mm smooth nodule)', '8 mm '),
                             # a word stands before the measure: it may be a position, and only closed words read
                             ('(at approximately 32 cm) linear erosions', None),
                             ('| at approximately 32 cm linear erosions |', None),
                             ('measured 2. 8 mm granular polyp', None), ('polyp - 8 mm granular polyp', None)):
            with self.subTest(phrase):
                self.assertEqual([m.group('size') for m in services.LESION.finditer(phrase) if m.group('size')],
                                 [size] if size else [])


class ObjectLesionTests(SimpleTestCase):
    """INV2-12: a lesion named as an act's object keeps its descriptive words between its determiner and its size."""

    def test_the_reviewers_objects_with_descriptive_words(self):
        for name in ('b11-additional-polyp', 'b12-second-polyp', 'b13-separate-small-polyp', 'b15-the-other-polyp',
                     'b14-ctrl'):
            with self.subTest(name):
                inv = read(fixture(name))
                colon = reconcile.service_for(inv, 'gi.colonoscopy')
                lesion = {les.id: (les.size, les.noun) for les in colon.lesions}
                self.assertEqual([lesion[a.lesion] for a in acts(inv, 'gi.colonoscopy', 'snare', ('performed',))],
                                 [('6 mm', 'polyp')])
                unresolved, bundled = unresolved_kinds(inv, [('45385', 'gi.colonoscopy')])
                self.assertIn(('gi.colonoscopy', 'biopsy'), unresolved)
                self.assertNotIn('biopsy', bundled)

    def test_own_shapes_of_an_objects_descriptive_words(self):
        for np, size in (('one further 8 mm polyp', '8 mm'), ('a large, flat 20 mm lesion', '20 mm'),
                         ('another small 6 mm polyp', '6 mm')):
            with self.subTest(np):
                inv = read(colo(f'Cold forceps biopsies of a 25 mm friable mass in the sigmoid colon and cold snare '
                                f'polypectomy of {np} in the rectum were performed.'))
                colon = reconcile.service_for(inv, 'gi.colonoscopy')
                lesion = {les.id: les.size for les in colon.lesions}
                self.assertEqual([lesion[a.lesion] for a in acts(inv, 'gi.colonoscopy', 'snare', ('performed',))], [size])
                self.assertIn(('gi.colonoscopy', 'biopsy'), unresolved_kinds(inv, [('45385', 'gi.colonoscopy')])[0])

    def test_words_that_are_no_lesions_own_never_join_an_act_to_it(self):
        """Control: a verb or a conjunction between an act and a lesion is no object phrase (LESION_OBJECT)."""
        for gap, joined in ((' of an additional ', True), (' of the other, ', True), (' of one further ', True),
                            (' were taken and ', False), (' and ', False), (' with ', False)):
            with self.subTest(gap):
                self.assertEqual(services.LESION_OBJECT.fullmatch(gap) is not None, joined)


class RemoteModalityTests(SimpleTestCase):
    """rev2-scope-11: an evaluation statement a remote modality leads or carries is no office visit for the inventory."""

    TEL = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nSaltmarsh Valley Gastroenterology '
           '(fictional)\nDate of service: 2026-10-21\n{title}\nPatient status: established\nPlace of service: office (POS '
           '11)\n{body}\nPhysician time: 8 minutes.\n')

    def office(self, text):
        return [s.status for s in read(text).services if s.family == 'gi.office_em']

    def test_the_reviewers_telephone_notes_document_no_office_visit(self):
        body = 'Called the patient two days after her colonoscopy. No bleeding or abdominal pain. Pathology pending.'
        for title in ('Telephone follow-up visit', 'Office visit via telephone'):
            with self.subTest(title):
                text = self.TEL.format(title=title, body=body)
                self.assertNotIn('performed', self.office(text))
                result = result_of(text, [])
                unresolved = next(c for c in result.encounter_checks if c.id == 'services.unresolved')
                self.assertNotIn('office / outpatient visit', unresolved.detail)
        text = self.TEL.format(title='Telephone follow-up visit', body=body)
        held = next(p for p in result_of(text, [('99212', 'Telephone follow-up visit')]).proposals)
        self.assertEqual(held.status, 'needs_clarification')
        self.assertFalse([c for c in held.checks if 'documented as performed' in c.detail])

    def test_own_shapes_of_a_remote_encounter(self):
        for title, body in (('GI clinic', 'Follow-up visit by phone two days after her colonoscopy. No bleeding.'),
                            ('E-mail consultation', 'Office visit summary requested by e-mail; no visit took place.'),
                            ('Telephone follow-up appointment', 'Called the patient; pathology benign.')):
            with self.subTest(title):
                self.assertNotIn('performed', self.office(self.TEL.format(title=title, body=body)))

    def test_an_office_visit_is_still_read(self):
        """Control: a clinic note's own evaluation statement."""
        text = self.TEL.format(title='GI clinic note', body='Seen in clinic for follow-up of constipation. Abdomen soft.')
        self.assertIn('performed', self.office(text))
        self.assertTrue(services._remote_statement('Office visit via telephone', 0, 12))
        line = 'Practice phone: 555-0100 is listed above.\nOffice visit'
        start = line.index('Office visit')
        self.assertFalse(services._remote_statement(line, start, start + 12))  # another line's field


class CostTests(SimpleTestCase):
    """The new reads stay linear: bounded work per relative clause, cell, row and heading line."""

    def test_an_act_with_many_relative_denials_is_read_in_bounded_work(self):
        """Each relative denial is read with one scan for the act's predicate before it (INV2-1): 400 sentences of
        relative denials after an act predicate and an act mention, about 120,000 characters."""
        sentence = ('The colonoscope was advanced and cold forceps biopsies, ' + 'which were not taken, ' * 12
                    + 'are planned. ')
        text = colo(sentence * 400)
        started = time.process_time()
        read(text)
        self.assertLess(time.process_time() - started, 30.0)

    def test_a_long_table_of_denied_and_timed_cells(self):
        rows = 'Colonoscopy | In 6 weeks | Yes, cold snare (no biopsies); forceps not used - none\n' * 4000
        text = HEAD + 'Colonoscopy report\nProcedure summary (no complications)\nExamination | Timing | Polypectomy\n' + rows
        started = time.process_time()
        read(text)
        self.assertLess(time.process_time() - started, 20.0)
