"""Session 7c8d38da, GI round 3, fix round 2 after the second independent refutation (lens extent: X1-X9).

Interpretation 51(e): an act or a status read from a table cell, a relative clause or a summary is performed only where
that cell or clause affirms it; otherwise it reads as the installed revision 90377ec6f413 reads it; a procedure section
opens only on positive evidence. 51(f): a closed list may only add positive evidence. Each finding is pinned by the
reviewer's own input (tests/fixtures/gi3/fix2_extent: the reviewer's synthetic texts, copied byte for byte), the
reviewer's variants, and shapes of our own beside it (another layout or heading, a paraphrase, another section, a
table, a PDF wrap), with controls the fix must not change:
- X1 (sections._report_title_words): a summary label opens a procedure section only under a title made of a procedure
  report's words, its aside included; a field line, a call's, a result's or an aftercare's note opens nothing;
- X2 (detect._extent_cell, sections.opened_on_evidence, sections.a_procedure_report): a table cell's extent is read only
  in a procedure's report, under a section opened on evidence;
- X3, X6 (sections._column_sense COLUMN_LANDMARK, _reach_contradicts): a landmark's reach column answers that reach and
  holds the row only where it leaves unaffirmed a reach the row's own extent covers;
- X4 (detect._analysis, _references, _doubt): a table's header row states nothing;
- X5 (sections._names_a_subject, layout; detect._later_denial, _cue_reading): every cell under a column that names its
  subject is a clause of its own, in a procedure's report, and never where it would part the service from a cell that
  reads with it;
- X7 (cues._POST_MODIFIER_PLACE): N1's post-modifier needs positive evidence of the act's own object or place;
- X8 (sections._column_sense, detect.UNSTATED_SUMMARY_ROW): a status word speaks for the row whatever stands beside it,
  and a summary row that states no extent says nothing of today's service;
- X9 (detect._relative_denial): a relative clause whose head is an act's noun denies that act.
Routing, the inventory and the engine are pure functions here: no database, no provider. Synthetic data only.
"""
import json
import time
import unittest
from datetime import date
from pathlib import Path

from studio.gi import cues, detect, sections
from studio.gi.context import extract_context
from studio.gi.detect import route, status_for_span
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode, RoutingResult, from_jsonable, to_jsonable
from studio.validation.engine import assess

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures' / 'gi3' / 'fix2_extent'
ROUND1 = HERE / 'fixtures' / 'gi3' / 'fix_extent'
GI3 = HERE / 'fixtures' / 'gi3'
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
NOT_READY = ('needs_clarification', 'excluded')
ADV = 'The colonoscope was advanced to the cecum, identified by the appendiceal orifice and the ileocecal valve.'
PASSED = 'The gastroscope was passed under direct vision to the second portion of the duodenum.'
SNARE = 'Both 5 mm sigmoid polyps were removed with a cold snare; pathology showed tubular adenomas.'
ROW = 'Colonoscopy | Adult colonoscope | Cecum | Two, sigmoid colon'
SUMMARY = 'Examination | Instrument | Furthest point reached | Polyps\n' + ROW


def fixture(name, where=FIXTURES):
    return (where / f'{name}.txt').read_text(encoding='utf-8')


def service_date(text):
    found = extract_context(text)['service_date']
    return date.fromisoformat(found.value) if found.origin in ('document', 'user') and found.value else None


def routed(text):
    """Routing as the pipeline stores it: for the document's own date, through JSON and back."""
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, service_date(text))))))


def finding(text, family):
    found = routed(text).finding(family)
    return (found.status, next((f.value for f in found.facts if f.name == 'extent'), None)) if found else None


def kinds(text):
    return [(s.kind, s.label) for s in sections.layout(text).sections]


def run_engine(text, picks):
    """picks: (code, [evidence passages]). The proposals by code (an empty reference)."""
    codes = []
    for index, (code, passages) in enumerate(picks):
        spans = tuple(EvidenceSpan(0, text.index(p), text.index(p) + len(p), p, True) for p in passages)
        codes.append(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', evidence=spans,
                                  index=index))
    result = assess(text=text, pages=(), context=extract_context(text), routing=routed(text),
                    normalized=NormalizedResponse('replay', 'gi3-fix2-extent', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=service_date(text),
                    provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}


def outcome(text, picks, code):
    proposal = run_engine(text, picks)[code]
    return proposal.status, [c.fact for c in proposal.clarifications]


def span_status(text, passage):
    at = text.index(passage)
    return status_for_span(text, at, at + len(passage), service_date(text))


def colon_report(table, title='Colonoscopy report', heading='Procedure summary', findings=ADV):
    return (BANNER + 'Harrowgate Endoscopy Unit (fictional)\n' + title + '\nPatient: Ingrid Vasquez-Holm (fictional)\n'
            'Date of procedure: 2026-10-20\nEndoscopist: Teodor Blackwood, MD (fictional)\n'
            'Site of care: hospital outpatient department, POS 22\n\nIndications\nAverage-risk screening.\n\n'
            + heading + '\n' + table + '\n\nFindings\n' + findings + ' Bowel preparation was excellent. The colonic '
            'mucosa was normal throughout.\n\nImpression\nNormal screening colonoscopy.\n\nPlan\nRepeat screening '
            'colonoscopy in 10 years.\nSigned: Teodor Blackwood, MD (fictional), 2026-10-20\n')


def egd_report(table, title='Upper endoscopy report'):
    return (BANNER + 'Quillan Bend Surgical Center (fictional)\n' + title + '\nDate of procedure: 2026-10-07\n'
            'Indications\nDyspepsia.\nProcedure summary\n' + table + '\nFindings\n' + PASSED + ' The gastric mucosa was '
            'normal.\nImpression\nNormal upper endoscopy.\n')


def office(title, body, table, time_line='Total time on the date of service: 30 minutes.', narrative=SNARE):
    return (BANNER + 'Larkspur Digestive Health (fictional)\n' + title + '\nPatient: Odalys Fenwick-Marr (fictional)\n'
            'Date of service: 2026-10-21\nPlace of service: office (POS 11)\nEstablished patient\n' + body + '\n'
            + table + '\n' + narrative + '\nAssessment:\nTwo small tubular adenomas.\nPlan:\nSurveillance colonoscopy '
            'in 7 years.\n' + time_line + '\n')


def reach_report(label, answer):
    """The reviewer's t3 report (reachsweep.py) with its last column renamed and answered."""
    base = fixture('t3-polyps-seen', ROUND1)
    text = base.replace('| Polyps seen\n', f'| {label}\n').replace('Colonoscopy | Adult colonoscope | Cecum | No',
                                                                  f'Colonoscopy | Adult colonoscope | Cecum | {answer}')
    assert f'| {label}\n' in text and f'Cecum | {answer}' in text
    return text


# --- X1: a summary label needs a title made of a procedure report's words ------------------------------------------------

class ReportTitleTests(unittest.TestCase):
    """sections._report_title_words: every word of the title line, its aside included."""

    def test_x1_the_reviewers_documents(self):
        cc1 = fixture('cc1')  # a field line ending with "report" was taken for the title
        self.assertFalse(sections._report_titled(cc1))
        self.assertNotIn(('procedure', 'procedure summary'), kinds(cc1))
        self.assertEqual(outcome(cc1, [('99213', ['Total time on the date of service: 25 minutes.']), ('45385', [ROW, SNARE])],
                                 '45385'), ('needs_clarification', ['performed_status', 'extent']))  # as installed
        cc2 = fixture('cc2-a5')  # the visit's own code is ready with no same-day procedure, as installed
        self.assertEqual(outcome(cc2, [('99213', ['Total time on the date of service: 25 minutes.'])], '99213'),
                         ('ready', []))
        call = fixture('f1-results-call')  # "Endoscopy note (post-procedure call)": the aside is read
        self.assertNotIn(('procedure', 'procedure summary'), kinds(call))
        self.assertEqual(outcome(call, [('45385', [ROW, SNARE])], '45385'),
                         ('needs_clarification', ['performed_status', 'extent']))

    def test_x1_the_reviewers_head_lines_and_titles(self):
        body = fixture('a4-cc-body')
        for line in ('Chief complaint: Discuss colonoscopy report', 'Chief complaint: discuss recent colonoscopy report',
                     'CC: review of colonoscopy report', 'Reason for referral: abnormal colonoscopy report',
                     'Referral reason: colonoscopy report', 'Presenting problem: abnormal EGD report',
                     'HPI: here to go over her colonoscopy report', 'Reason for visit: discuss colonoscopy report',
                     'Chief complaint: colonoscopy results', 'Concern: colonoscopy pathology report'):
            with self.subTest(line=line):
                text = body.replace('{TITLE}', line)
                self.assertFalse(sections._report_titled(text))
                self.assertNotEqual(outcome(text, [('45385', [ROW, SNARE])], '45385')[0], 'ready')
        results = fixture('results-body')
        for title in ('Endoscopy note (post-procedure call)', 'Endoscopy note (pre-procedure)', 'Colonoscopy report (prior)',
                      'Colonoscopy report (outside facility)', 'Endoscopy telephone note', 'Endoscopy results note',
                      'Post-colonoscopy call note', 'Post-colonoscopy telephone note', 'Pre-colonoscopy assessment note',
                      'Pre-colonoscopy nursing note', 'Post-EGD note', 'Pre-ERCP note', 'Colonoscopy pre-assessment note',
                      'Post-polypectomy call note', 'Colonoscopy aftercare note', 'Colonoscopy discharge note'):
            with self.subTest(title=title):
                text = results.replace('{TITLE}', title)
                self.assertFalse(sections._report_titled(text))
                self.assertNotIn(('procedure', 'procedure summary'), kinds(text))
                self.assertNotEqual(outcome(text, [('45385', [ROW, SNARE])], '45385')[0], 'ready')

    def test_x1_our_own_shapes(self):
        # an aside naming another document, a capitals title naming another place, a bold field line, an EGD result
        # note, a call's title with a dash, and a PDF wrap of a follow-up title: none opens the summary
        for title in ('Colonoscopy report (copy for the clinic file)', 'COLONOSCOPY REPORT - OUTSIDE FACILITY',
                      '**Reason for visit:** discuss EGD report', 'EGD results note',
                      'Telephone encounter - colonoscopy results', 'Endoscopy follow-up\nnote', 'Colonoscopy report review'):
            with self.subTest(title=title):
                text = office(title, 'Called with results.', 'Procedure summary\n' + SUMMARY)
                self.assertNotIn(('procedure', 'procedure summary'), kinds(text))
                self.assertIn(outcome(text, [('45385', [ROW, SNARE])], '45385')[0], NOT_READY)

    def test_control_a_procedure_reports_title_still_opens_it(self):
        for title in ('Colonoscopy report (amended)', 'EGD and colonoscopy report (final)',
                      'Procedure note - colonoscopy with cold snare polypectomy', 'Brief operative note', 'GI procedure note',
                      'Outpatient Endoscopy Unit - Colonoscopy Report', 'Combined upper and lower endoscopy report'):
            with self.subTest(title=title):
                text = colon_report(SUMMARY, title=title, findings=ADV + ' ' + SNARE)
                self.assertTrue(sections._report_titled(text))
                self.assertIn(('procedure', 'procedure summary'), kinds(text))
                self.assertEqual(outcome(text, [('45385', [ROW, SNARE])], '45385'), ('ready', []))
        for name, egd, colon in (('h2-01__9468f9c1__2026-10-29.txt', 'third part of duodenum', 'terminal ileum'),):
            text = (GI3 / name).read_text(encoding='utf-8')
            self.assertEqual(finding(text, 'gi.egd'), ('performed', egd))
            self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', colon))

    def test_the_title_words(self):
        for line in ('Colonoscopy report', 'PROCEDURE NOTE: EGD WITH BAND LIGATION', 'Colonoscopy Report - Surveillance',
                     'Endoscopic ultrasound procedure report', 'Colonoscopy report (preliminary)'):
            with self.subTest(line=line):
                self.assertTrue(sections._report_title_words(line))
        for line in ('Colonoscopy report (2024)', 'Chief complaint: colonoscopy report', 'Endoscopy telephone note',
                     'Colonoscopy aftercare note', 'Larkspur Endoscopy Center Colonoscopy Report'):
            with self.subTest(line=line):
                self.assertFalse(sections._report_title_words(line))


# --- X2: a table cell's extent only in a procedure's report, under a section opened on evidence -------------------------

class TableExtentEvidenceTests(unittest.TestCase):
    """detect._extent_cell: sections.a_procedure_report and sections.opened_on_evidence."""

    def test_x2_the_reviewers_documents(self):
        follow = fixture('f8-followup')  # "Colonoscopy follow-up note" opens a procedure section by the old title rule
        self.assertEqual(finding(follow, 'gi.colonoscopy')[1], None)
        proposals = run_engine(follow, [('99214', ['Total time on the date of service: 45 minutes.']), ('45385', [ROW, SNARE])])
        self.assertEqual((proposals['45385'].status, [c.fact for c in proposals['45385'].clarifications]),
                         ('needs_clarification', ['extent']))  # as installed: the extent is asked
        consult = fixture('f8-consult')
        self.assertEqual(outcome(consult, [('99204', ['Total time on the date of service: 45 minutes.']), ('45385', [ROW, SNARE])],
                                 '45385'), ('needs_clarification', ['extent']))

    def test_x2_the_reviewers_titles(self):
        body = fixture('consult-body')
        for title in ('Colonoscopy follow-up note', 'Colonoscopy clinic note', 'Colonoscopy results review note',
                      'Post-colonoscopy follow-up note', 'EGD follow-up note', 'Progress Note'):
            with self.subTest(title=title):
                text = body.replace('{TITLE}', title)
                self.assertIsNone(finding(text, 'gi.colonoscopy')[1])
                self.assertIn(outcome(text, [('45385', [ROW, SNARE])], '45385')[0], NOT_READY)

    def test_x2_our_own_shapes(self):
        # a consultation titled by another service, an office follow-up's "Findings:" heading (a section opened on its
        # heading, in no procedure's report), a PDF-wrapped follow-up title, a return visit's "Procedure:" heading
        for title, body in (('EGD consultation note', 'Reason for consultation: review of an outside colonoscopy.'),
                            ('Gastroenterology follow-up', 'Reason for visit: review of her outside colonoscopy.\nFindings:'),
                            ('Colonoscopy\nfollow-up note', 'Reason for visit: her outside colonoscopy.'),
                            ('Clinic note - return visit', 'Reason for visit: outside colonoscopy.\nProcedure:')):
            with self.subTest(title=title, body=body):
                text = office(title, body, SUMMARY)
                self.assertIsNone(finding(text, 'gi.colonoscopy')[1])
                self.assertIn(outcome(text, [('45385', [ROW, SNARE])], '45385')[0], NOT_READY)

    def test_control_a_reports_own_table_still_reads_its_extent(self):
        for heading in ('Procedure summary', 'Findings:', 'Procedure:'):
            with self.subTest(heading=heading):
                text = colon_report('Examination | Instrument | Furthest point reached\nColonoscopy | Adult colonoscope | '
                                    'Hepatic flexure', heading=heading, findings='Bowel preparation was poor.')
                self.assertEqual(finding(text, 'gi.colonoscopy')[1], 'incomplete: hepatic flexure')
        self.assertTrue(sections.a_procedure_report(colon_report(SUMMARY)))
        self.assertFalse(sections.a_procedure_report(fixture('f8-followup')))


# --- X3, X6: a landmark's reach column answers that reach ----------------------------------------------------------------

class ReachColumnTests(unittest.TestCase):
    """sections._column_sense COLUMN_LANDMARK, _reach_contradicts, TABLE_ROW_REACH_HELD_LABEL."""

    def test_x3_x6_the_reviewers_documents(self):
        for name in ('f10-ti-not', 't3-ti'):  # "TI not intubated | Yes", "TI intubated | No" under a cecum extent
            text = fixture(name)
            with self.subTest(name=name):
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                self.assertEqual(outcome(text, [('45378', [ADV])], '45378'), ('ready', []))

    def test_x3_x6_the_reviewers_labels(self):
        for label, answer in (('Terminal ileum intubated', 'No'), ('TI intubated', 'No'), ('Terminal ileum examined', 'No'),
                              ('Terminal ileum', 'No'), ('Ileocecal valve intubated', 'No'),
                              ('Appendiceal orifice photographed', 'No'), ('Cecum photographed', 'No'),
                              ('Terminal ileum not intubated', 'Yes'), ('TI not intubated', 'Yes'),
                              ('Terminal ileum not examined', 'Yes'), ('Terminal ileum not reached', 'Yes'),
                              ('Ileocecal valve not intubated', 'Yes'), ('Cecum not photographed', 'Yes'),
                              ('Not photographed', 'Yes'), ('Not documented', 'Yes'), ('Ileum intubated', 'No')):
            with self.subTest(label=label):
                text = reach_report(label, answer)
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                row = f'Colonoscopy | Adult colonoscope | Cecum | {answer}'
                self.assertEqual(outcome(text, [('45378', [ADV])], '45378'), ('ready', []))
                self.assertEqual(outcome(text, [('45378', [row])], '45378'), ('ready', []))

    def test_x3_x6_our_own_shapes(self):
        egd = egd_report('Examination | Instrument | Furthest point reached | Jejunum entered\nUpper endoscopy (EGD) | '
                         'Standard gastroscope | Second portion of the duodenum | No')  # EGD: the jejunum lies beyond D2
        self.assertEqual(outcome(egd, [('43235', [PASSED])], '43235'), ('ready', []))
        negated_no = colon_report('Examination | Furthest point reached | TI not intubated\nColonoscopy | Cecum | No')
        self.assertEqual(outcome(negated_no, [('45378', [ADV])], '45378'), ('ready', []))
        findings = colon_report('Examination | Extent | TI intubated\nColonoscopy | Cecum | No', heading='Findings:')
        self.assertEqual(outcome(findings, [('45378', [ADV])], '45378'), ('ready', []))
        bidi = (BANNER + 'Northgate Endoscopy (fictional)\nBidirectional Endoscopy Report\nDate of procedure: 2026-10-20\n'
                'Indications\nAnemia.\nProcedure summary\nExamination | Extent | TI intubated\nUpper endoscopy (EGD) | '
                'Second portion of the duodenum | N/A\nColonoscopy | Cecum | No\nFindings\n' + PASSED + ' ' + ADV
                + '\nImpression\nNormal.\n')  # the TI is no landmark of the EGD row's tract
        proposals = run_engine(bidi, [('43235', [PASSED]), ('45378', [ADV])])
        self.assertEqual((proposals['43235'].status, proposals['45378'].status), ('ready', 'ready'))
        sig = colon_report('Examination | Instrument | Furthest point reached | Splenic flexure passed\nFlexible '
                           'sigmoidoscopy | Sigmoidoscope | Descending colon | No', title='Flexible sigmoidoscopy report',
                           findings='The sigmoidoscope was advanced to the descending colon.')
        self.assertEqual(outcome(sig, [('45330', ['The sigmoidoscope was advanced to the descending colon.'])], '45330'),
                         ('ready', []))

    def test_control_a_reach_the_rows_extent_covers_holds_it(self):
        for table in ('Examination | Furthest point reached | Cecum reached\nColonoscopy | Cecum | No',
                      'Examination | Furthest point reached | Cecum reached\nColonoscopy | 60 cm | No',  # a depth: unplaced
                      'Examination | Extent | Terminal ileum\nColonoscopy | Terminal ileum | No',
                      'Examination | Furthest point reached | Cecum reached\nColonoscopy | Cecum | -'):
            with self.subTest(table=table):
                text = colon_report(table)
                self.assertIn(('other', sections.TABLE_ROW_REACH_HELD_LABEL), kinds(text))
                self.assertEqual(outcome(text, [('45378', [ADV])], '45378')[0], 'needs_clarification')
        # the reviewer's "Appendiceal orifice not seen | Yes" against "identified by the appendiceal orifice": the row
        # contradicts the report's own cecal landmark, so it is held (asked), never ready
        text = reach_report('Appendiceal orifice not seen', 'Yes')
        self.assertEqual(outcome(text, [('45378', [ADV])], '45378')[0], 'needs_clarification')
        for label, answer in (('Cecum reached', 'Yes'), ('Cecum reached', 'Reached'), ('Terminal ileum', 'Normal')):
            with self.subTest(label=label, answer=answer):  # an affirmed reach is consistent
                self.assertEqual(outcome(reach_report(label, answer), [('45378', [ADV])], '45378'), ('ready', []))

    def test_the_senses(self):
        for label, sense in (('ti intubated', sections.COLUMN_LANDMARK), ('cecum not photographed', sections.COLUMN_OWN),
                             ('not documented', sections.COLUMN_OWN), ('terminal ileum', sections.COLUMN_LANDMARK),
                             ('ileum intubated', sections.COLUMN_OWN), ('reached', sections.COLUMN_ROW),
                             ('furthest point reached', sections.COLUMN_ROW)):
            with self.subTest(label=label):
                self.assertEqual(sections._column_sense(label), sense)
        self.assertEqual(sections._label_reach('ileocecal valve intubated'), ([('lower', 9)], False))
        self.assertEqual(sections._label_reach('ti not intubated'), ([('lower', 9)], True))


# --- X4: a header row states nothing -------------------------------------------------------------------------------------

class HeaderWordTests(unittest.TestCase):
    """detect._analysis, _references and _doubt read nothing on a table's header line."""

    def test_x4_the_reviewers_documents(self):
        for name in ('t3-terminated', 't3-aborted', 't3-discontinued'):
            text = fixture(name)
            with self.subTest(name=name):
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                self.assertEqual(outcome(text, [('45378', [ADV])], '45378'), ('ready', []))
        n1 = fixture('n1-cancelled-col', ROUND1)  # a provider cites the header row with the EGD row
        header = 'Examination | Instrument | Furthest point reached | Cancelled\n'
        egd_row = 'Upper endoscopy (EGD) | Standard gastroscope | Second portion of the duodenum | No'
        proposals = run_engine(n1, [('43239', [header + egd_row]),
                                    ('45378', [header + egd_row + '\nColonoscopy | Adult colonoscope | - | Yes'])])
        self.assertEqual(proposals['43239'].status, 'ready')
        self.assertFalse(any('cancelled' in c.detail for c in proposals['43239'].checks if c.status != 'pass'))
        self.assertEqual(proposals['45378'].status, 'needs_clarification')

    def test_x4_our_own_shapes(self):
        for label in ('Incomplete', 'Postponed', 'Not performed', 'Stopped early'):
            with self.subTest(label=label):
                text = egd_report(f'Examination | Instrument | Furthest point reached | {label}\nUpper endoscopy (EGD) | '
                                  'Standard gastroscope | Second portion of the duodenum | No')
                self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
                self.assertEqual(outcome(text, [('43235', [PASSED])], '43235'), ('ready', []))

    def test_control_a_statement_outside_the_table_still_reads(self):
        text = colon_report('Examination | Instrument | Furthest point reached\nColonoscopy | Adult colonoscope | Hepatic '
                            'flexure', findings='The procedure was terminated early at the hepatic flexure because of looping.')
        self.assertEqual(finding(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: hepatic flexure'))
        cancelled = fixture('n1-cancelled-col', ROUND1)
        self.assertNotIn(finding(cancelled, 'gi.colonoscopy')[0], ('performed', 'incomplete'))  # "Cancelled | Yes" holds


# --- X5: an answer under a column that names its subject -------------------------------------------------------------

class SubjectColumnTests(unittest.TestCase):
    """sections._names_a_subject and the layout's cuts; detect._later_denial and _cue_reading skip such cells."""

    def test_x5_the_reviewers_documents(self):
        for name, picks in (('f2-none-noted', [ADV]), ('b1-nottaken', [ADV]),
                            ('b1-nottaken', ['Colonoscopy | Cecum | Not taken | Not performed | Not placed'])):
            text = fixture(name)
            with self.subTest(name=name, picks=picks):
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                self.assertEqual(outcome(text, [('45378', picks)], '45378'), ('ready', []))
        h201 = fixture('h2-01-nonetaken')  # h2-01 with "Tissue sampled | None taken"
        self.assertEqual(finding(h201, 'gi.colonoscopy'), ('performed', 'terminal ileum'))

    def test_x5_the_reviewers_answers(self):
        for label, answer in (('Complications', 'None noted'), ('Complications', 'None reported'),
                              ('Specimens', 'Not applicable'), ('Specimens', 'None sent'), ('Pathology', 'Not sent'),
                              ('Biopsies', 'None taken'), ('Biopsies', 'No (normal mucosa)'), ('Polypectomy', 'Not required'),
                              ('Pathology', 'Pending')):
            with self.subTest(label=label, answer=answer):
                text = reach_report(label, answer)
                row = f'Colonoscopy | Adult colonoscope | Cecum | {answer}'
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                self.assertEqual(outcome(text, [('45378', [ADV])], '45378'), ('ready', []))
                self.assertEqual(outcome(text, [('45378', [row])], '45378'), ('ready', []))

    def test_x5_our_own_shapes(self):
        egd = egd_report('Examination | Instrument | Furthest point reached | Biopsies\nUpper endoscopy (EGD) | Standard '
                         'gastroscope | Second portion of the duodenum | None obtained')
        self.assertEqual(outcome(egd, [('43235', [PASSED])], '43235'), ('ready', []))
        nil = colon_report('Examination | Instrument | Furthest point reached | Complications\nColonoscopy | Adult '
                           'colonoscope | Cecum | Nil reported')
        self.assertEqual(outcome(nil, [('45378', [ADV])], '45378'), ('ready', []))
        findings = colon_report('Examination | Instrument | Furthest point reached | Specimens\nColonoscopy | Adult '
                                'colonoscope | Cecum | Not sent to pathology', heading='Findings:')
        self.assertEqual(outcome(findings, [('45378', [ADV])], '45378'), ('ready', []))
        aborted = colon_report('Examination | Instrument | Furthest point reached | Complications\nColonoscopy | Adult '
                               'colonoscope | - | Procedure aborted for bleeding', findings='Bowel preparation was poor.')
        self.assertEqual(outcome(aborted, [('45378', ['Colonoscopy | Adult colonoscope | - | Procedure aborted for '
                                                      'bleeding'])], '45378')[0], 'needs_clarification')

    def test_control_a_cut_never_parts_the_service_from_its_own_status(self):
        # a first-fix-round hole: cutting the biopsy's "No" left the performed "No" out of the colonoscopy's clause
        text = (BANNER + 'Harrowgate Endoscopy Unit (fictional)\nCombined upper and lower endoscopy report\nDate of '
                'procedure: 2026-10-20\nIndications\nAnemia.\nProcedure summary\nExamination | Biopsy | Performed | '
                'Furthest point reached\nUpper endoscopy (EGD) | Yes | Yes | Second portion of the duodenum\nColonoscopy | '
                'No | No | -\nImpression\nSee above.\n')
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        nothing = (BANNER + 'Harrowgate Endoscopy Unit (fictional)\nCombined upper and lower endoscopy report\nDate of '
                   'procedure: 2026-10-20\nIndications\nAnemia.\nProcedure summary\nExamination | Instrument | Extent\n'
                   'Upper endoscopy (EGD) | Gastroscope | Second portion of the duodenum\nColonoscopy | Colonoscope | None\n'
                   'Impression\nSee above.\n')
        self.assertNotIn(finding(nothing, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        comment = colon_report('Examination | Instrument | Furthest point reached | Comments\nColonoscopy | Adult colonoscope '
                               '| Cecum | Not performed')
        self.assertEqual(outcome(comment, [('45378', [ADV])], '45378')[0], 'needs_clarification')

    def test_control_an_office_notes_pasted_table_is_read_whole(self):
        # a first-fix-round hole too: the bare "None" was cut in an office follow-up and the outside colonoscopy read
        # performed today (45378 ready); no cut is made outside a procedure's report
        for answer in ('None', 'None noted'):
            with self.subTest(answer=answer):
                text = office('Gastroenterology follow-up', 'Reason for visit: review of her outside colonoscopy.\n'
                              'Findings:', 'Examination | Instrument | Furthest point reached | Complications\nColonoscopy '
                              f'| Adult colonoscope | Cecum | {answer}',
                              narrative='The colonoscope was advanced to the cecum; the mucosa was normal.')
                self.assertEqual(sections.layout(text).answer_cells, ())
                self.assertIn(outcome(text, [('45378', ['The colonoscope was advanced to the cecum; the mucosa was '
                                                        'normal.'])], '45378')[0], NOT_READY)


# --- X7: N1's post-modifier needs positive evidence ----------------------------------------------------------------------

class OccasionTests(unittest.TestCase):
    """cues._POST_MODIFIER_PLACE."""

    def test_x7_the_reviewers_document_and_phrases(self):
        text = fixture('p-thattime')
        self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
        self.assertEqual(outcome(text, [('45378', [ADV])], '45378'), ('ready', []))
        post = cues.NEGATED_POST[0][1]
        for phrase in ('at that time', 'at the time', 'on admission', 'in the hospital', 'at the referring hospital',
                       'at the community hospital', 'at diagnosis', 'at presentation', 'in the emergency department',
                       'at baseline', 'in childhood', 'at her local hospital', 'at Riverside General', 'in the ICU',
                       'on that admission', 'at that admission', 'on the ward', 'at the screening program',
                       'at the initial evaluation', 'at his first visit', 'at transfer'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(post.search(f' {phrase} was not performed because of poor preparation.'))

    def test_x7_our_own_shapes(self):
        for sentence in ('Colonoscopy during the previous admission was not performed because of instability.',
                         'Colonoscopy at Larkspur Memorial was not performed because of a poor preparation.',
                         'Colonoscopy at that\ntime was not performed because of instability.'):
            with self.subTest(sentence=sentence):
                text = colon_report('Examination | Instrument | Furthest point reached\nColonoscopy | Adult colonoscope | '
                                    'Cecum').replace('Average-risk screening.', 'Hematochezia. ' + sentence)
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                self.assertEqual(outcome(text, [('45378', [ADV])], '45378'), ('ready', []))

    def test_control_the_acts_own_object_or_place_still_carries_it(self):
        post = cues.NEGATED_POST[0][1]
        for tail in (' of the channel was not attempted', ' of the cecum were not obtained', ' at the bedside was not performed',
                     ' across the narrowed pyloric channel was not performed', ' of the gastric antrum was not performed'):
            with self.subTest(tail=tail):
                self.assertIsNotNone(post.search(tail))
        text = egd_report('Examination | Instrument | Furthest point reached\nUpper endoscopy (EGD) | Standard gastroscope | '
                          'Second portion of the duodenum').replace(' The gastric mucosa was normal.',
                                                                    ' Biopsy of the gastric antrum was not performed.')
        self.assertIn(outcome(text, [('43239', ['Biopsy of the gastric antrum was not performed.'])], '43239')[0], NOT_READY)


# --- X8: a status word speaks for the row; a summary row that states no extent says nothing --------------------------------

class UnstatedRowTests(unittest.TestCase):
    """sections._column_sense (a status word beside any other word) and detect.UNSTATED_SUMMARY_ROW."""

    def test_x8_the_reviewers_documents(self):
        for name, row in (('n1-session', 'Colonoscopy | Adult colonoscope | - | No'),
                          ('n1-rescheduled', 'Colonoscopy | Adult colonoscope | - | Yes')):
            text = fixture(name)
            with self.subTest(name=name):
                self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
                self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
                proposals = run_engine(text, [('43239', [PASSED]), ('45378', [row])])
                self.assertEqual((proposals['43239'].status, proposals['45378'].status), ('ready', 'needs_clarification'))

    def test_x8_the_reviewers_labels(self):
        base = fixture('n1-cancelled-col', ROUND1)
        for label, egd, colon in (('Performed this session', 'Yes', 'No'), ('Completed successfully', 'Yes', 'No'),
                                  ('Performed as planned', 'Yes', 'No'), ('Performed by endoscopist', 'Yes', 'No'),
                                  ('Performed under anesthesia', 'Yes', 'No'), ('Completed per protocol', 'Yes', 'No'),
                                  ('Done this session', 'Yes', 'No'), ('Rescheduled', 'No', 'Yes'), ('Declined', 'No', 'Yes'),
                                  ('Refused', 'No', 'Yes'), ('Not started', 'No', 'Yes'), ('Withdrawn', 'No', 'Yes'),
                                  ('Omitted', 'No', 'Yes'), ('Skipped', 'No', 'Yes'), ('Cancelled by patient', 'No', 'Yes'),
                                  ('Cancelled on the day', 'No', 'Yes'), ('Aborted early', 'No', 'Yes')):
            with self.subTest(label=label):
                text = base.replace('| Cancelled\n', f'| {label}\n').replace(
                    'Second portion of the duodenum | No', f'Second portion of the duodenum | {egd}').replace(
                    'Colonoscopy | Adult colonoscope | - | Yes', f'Colonoscopy | Adult colonoscope | - | {colon}')
                self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
                self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))

    def test_x8_our_own_shapes(self):
        for label, answer in (('Outcome', 'Rebooked'), ('Comments', 'Patient chose to reschedule'), ('Declined', 'Yes')):
            with self.subTest(label=label):
                row = 'Colonoscopy | Adult colonoscope | - | ' + answer
                text = (BANNER + 'Brightwater Valley Endoscopy Center (fictional)\nCombined upper and lower endoscopy '
                        'report\nProcedure date: 2026-10-16\nIndications\nAnemia.\nProcedure summary\nExamination | '
                        f'Instrument | Furthest point reached | {label}\nUpper endoscopy (EGD) | Standard gastroscope | '
                        f'Second portion of the duodenum | -\n{row}\nUpper endoscopy\n{PASSED}\nImpression\nNormal EGD.\n')
                proposals = run_engine(text, [('43235', [PASSED]), ('45378', [row])])
                self.assertEqual((proposals['43235'].status, proposals['45378'].status), ('ready', 'needs_clarification'))
                self.assertEqual(span_status(text, 'Colonoscopy')[0], 'uncertain')

    def test_control_a_rows_own_denial_still_contradicts(self):
        text = (BANNER + 'Harrowgate Endoscopy Unit (fictional)\nColonoscopy report\nDate of procedure: 2026-10-20\n'
                'Indications\nAnemia.\nProcedure summary\nExamination | Performed | Furthest point reached\nUpper endoscopy '
                '(EGD) | Yes | Second portion of the duodenum\nColonoscopy | No | -\nFindings\n' + ADV + '\nImpression\nSee '
                'above.\n')
        status, cues_ = span_status(text, 'Colonoscopy | No | -')
        self.assertEqual(status, 'uncertain')
        self.assertNotIn(detect.UNSTATED_SUMMARY_ROW, cues_)  # the row's own "No" is read first, as a doubt
        self.assertNotEqual(finding(text, 'gi.colonoscopy')[0], 'performed')


# --- X9: a relative clause whose head is an act's noun ---------------------------------------------------------------------

class RelativeActHeadTests(unittest.TestCase):
    """detect._relative_denial: an act's noun as the head denies that act, as at 90377ec6f413."""

    def test_x9_the_reviewers_documents(self):
        text = fixture('f7-sampling')
        sentence = 'Sampling, which was not performed because of the bleeding risk, will follow at the repeat examination.'
        self.assertEqual(span_status(text, sentence)[0], 'negated')
        self.assertEqual(run_engine(text, [('45380', [sentence])])['45380'].status, 'excluded')

    def test_x9_the_reviewers_sentences_and_ours(self):
        for code, sentence, expected in (
                ('45380', 'Specimens, which were not obtained because of the bleeding risk, would have gone to pathology.',
                 ('excluded',)),
                ('45380', 'Samples, which were not taken because of the anticoagulation, are planned at the repeat '
                          'examination.', ('excluded',)),
                ('45380', 'The specimen that was not obtained today will be taken at the repeat examination.', ('excluded',)),
                ('45380', 'Biopsy, which was not obtained because of anticoagulation, is planned.', NOT_READY),
                ('45385', 'Polypectomy, which was not performed because of the INR, will follow.', NOT_READY),
                ('45380', 'The sampling that was not done today is planned at the repeat examination.', NOT_READY),
                # known limits: a head that names the thing the act treats keeps the denial its own (held, never ready)
                ('45380', 'Tissue, which was not sampled because of the bleeding risk, will be taken at the repeat '
                          'examination.', ('needs_clarification',)),
                ('45385', 'The lesion, which was not resected because of its size, was referred for surgery.',
                 ('needs_clarification',))):
            with self.subTest(sentence=sentence):
                text = colon_report('Examination | Instrument | Furthest point reached\nColonoscopy | Adult colonoscope | '
                                    'Cecum', findings=ADV + ' ' + sentence)
                self.assertIn(run_engine(text, [(code, [sentence])])[code].status, expected)

    def test_control_the_polyp_that_was_not_removed(self):
        for name, sentence in (('rel-r2', 'Biopsies were taken with cold forceps from the polyp that was not removed'),):
            text = fixture(name, ROUND1)
            self.assertEqual(span_status(text, sentence)[0], 'performed')
            self.assertNotEqual(run_engine(text, [('45380', [sentence])])['45380'].status, 'excluded')


# --- cost: every new loop and pattern is linear --------------------------------------------------------------------------

class CostTests(unittest.TestCase):
    """Process time at sizes a quadratic shape fails at once."""

    def timed(self, build, size):
        text = build(size)
        sections.layout.cache_clear()
        detect._analysis.cache_clear()
        start = time.process_time()
        route(text, date(2026, 10, 20))
        elapsed = time.process_time() - start
        sections.layout.cache_clear()
        detect._analysis.cache_clear()
        return elapsed

    def assert_linear(self, build, small=4000, large=16000, limit=20.0):
        a, b = self.timed(build, small), self.timed(build, large)
        self.assertLess(b, limit)
        self.assertLess(b, 8 * a + 0.5)  # four times the size: a quadratic shape takes sixteen times as long

    def test_a_wide_landmark_table(self):
        def build(n):  # one header of n landmark columns over one row: each cell's reach read once per row
            header = 'Examination | Furthest point reached | ' + ' | '.join(['Cecum reached'] * (n // 16))
            row = 'Colonoscopy | Cecum | ' + ' | '.join(['No'] * (n // 16))
            return colon_report(header + '\n' + row)
        self.assert_linear(build)

    def test_many_summary_rows_that_state_no_extent(self):
        def build(n):
            rows = '\n'.join(f'Colonoscopy | Adult colonoscope | - | Yes' for _ in range(n // 40))
            return colon_report('Examination | Instrument | Furthest point reached | Rescheduled\nUpper endoscopy (EGD) | '
                                'Gastroscope | Second portion of the duodenum | No\n' + rows)
        self.assert_linear(build)

    def test_many_subject_cells(self):
        def build(n):
            rows = '\n'.join('Colonoscopy | Adult colonoscope | Cecum | None noted' for _ in range(n // 50))
            return colon_report('Examination | Instrument | Furthest point reached | Complications\n' + rows)
        self.assert_linear(build)

    def test_relative_heads_and_post_modifiers(self):
        def build(n):
            sentence = ('Sampling, which was not performed because of the bleeding risk, will follow. Colonoscopy at that '
                        'time was not performed. ')
            return colon_report('Examination | Instrument | Furthest point reached\nColonoscopy | Adult colonoscope | '
                                'Cecum', findings=ADV + ' ' + sentence * (n // len(sentence)))
        self.assert_linear(build)

    def test_a_long_title_line_and_blank_runs(self):
        start = time.process_time()
        self.assertFalse(sections._report_title_words('Colonoscopy report ' + 'x ' * 50_000))
        post = cues.NEGATED_POST[0][1]
        self.assertIsNone(post.search(' of the' + ' ' * 100_000 + 'x was not performed'))
        self.assertLess(time.process_time() - start, 1.0)


if __name__ == '__main__':
    unittest.main()
