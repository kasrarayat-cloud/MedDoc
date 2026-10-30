"""Session 7c8d38da, GI round 3, fix round 1 after the independent refutation (lenses extent and cost).

Each finding is pinned by the reviewer's own input (tests/fixtures/gi3/fix_extent: the reviewer's synthetic texts,
copied byte for byte) and its source-correct output, beside a control the fix must not change:
- EXT-1, EXT-3 (sections._report_titled): a procedure-summary label opens a procedure section only under a procedure
  report's title, never under an office note's ("Progress Note", "Gastroenterology Consultation", "Telehealth Visit", ...),
  so a pasted colonoscopy table never makes 45385 ready nor asks 99213/99204 about a same-day procedure;
- EXT-4 (sections._column_sense): a finding's or an act's column ("Polyps seen", "Antrum biopsy", "Retroflexion in
  rectum") answers itself, so its "No" never doubts the examination;
- EXT-5 (detect._doubt, sections.Layout.answers_its_column): a cited table row never takes the answer cells that answer
  their own columns;
- EXT-6 (cues._POST_MODIFIER_WORD): an occasion phrase ("at the outside hospital", "at age 50", "in the last ten years")
  is no post-modifier of today's act;
- EXT-7 (sections._column_sense, layout, detect._default_reading): a not-done status column ("Cancelled") reads with the
  opposite sense: "No" answers itself, anything else holds the row;
- EXT-2, routing's half (detect._relative_denial, cues.INTERVENTIONS' cold forceps removal): a denial inside a relative
  clause is its head noun's, never the passage's act;
- cost-1 (sections._TABLE_ANSWER_CELL, and the same shape in _SEC_NO_ANSWER): blank runs read once.
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
FIXTURES = HERE / 'fixtures' / 'gi3' / 'fix_extent'
GI3 = HERE / 'fixtures' / 'gi3'
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
H2_01 = 'h2-01__9468f9c1__2026-10-29.txt'


def fixture(name):
    return (FIXTURES / f'{name}.txt').read_text(encoding='utf-8')


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
                    normalized=NormalizedResponse('replay', 'gi3-fix-extent', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=service_date(text),
                    provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}


def clarified(proposal):
    return [c.fact for c in proposal.clarifications]


def warned(proposal):
    return [c.id for c in proposal.checks if c.status not in ('pass', 'not_applicable')]


def span_status(text, passage):
    at = text.index(passage)
    return status_for_span(text, at, at + len(passage), service_date(text))


SNARE = 'Both 5 mm sigmoid polyps were removed with a cold snare; pathology showed tubular adenomas.'
ROW = 'Colonoscopy | Adult colonoscope | Cecum | Two, sigmoid colon'
TIME_25 = 'Total time on the date of service: 25 minutes.'
OFFICE_TITLES = ('Progress Note', 'Office progress note', 'Gastroenterology Consultation', 'New Patient Visit',
                 'Telehealth Visit', 'Established patient visit')


# --- EXT-1, EXT-3: the summary label needs a procedure report's title ----------------------------------------------------

class OfficeTitleTests(unittest.TestCase):
    """A pasted colonoscopy table in an office note is asked, never today's procedure (sections._report_titled)."""

    def test_ext1_a_progress_notes_pasted_table_never_makes_45385_ready(self):
        text = fixture('a4-soap')
        self.assertNotIn(('procedure', 'procedure summary'), kinds(text))
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        # as at 90377ec6f413, for each citation the reviewer tried: held, the extent asked (no table's extent is read)
        for passages, asked in (([ROW, SNARE], ['performed_status', 'extent']), ([ROW], ['extent']),
                                ([SNARE], ['performed_status', 'extent'])):
            with self.subTest(passages=passages):
                proposals = run_engine(text, [('99213', [TIME_25]), ('45385', passages)])
                self.assertEqual((proposals['45385'].status, clarified(proposals['45385'])), ('needs_clarification', asked))

    def test_ext1_every_office_title_the_visit_class_missed(self):
        base = fixture('a4-soap')
        self.assertEqual(base.count('\nProgress Note\n'), 1)
        for title in OFFICE_TITLES:
            text = base.replace('\nProgress Note\n', f'\n{title}\n')
            with self.subTest(title=title):
                self.assertFalse(sections._report_titled(text))
                self.assertNotIn(('procedure', 'procedure summary'), kinds(text))
                self.assertNotEqual(run_engine(text, [('45385', [ROW, SNARE])])['45385'].status, 'ready')
        for name in ('a4-title', 'a3-progress', 'a1-consult'):  # "Telehealth Visit", "Office progress note", a consult
            with self.subTest(name=name):
                self.assertNotIn(('procedure', 'procedure summary'), kinds(fixture(name)))

    def test_ext3_the_visits_own_code_is_ready_with_no_same_day_procedure(self):
        for name, code in (('a5-soap', '99213'), ('a2-consult', '99204')):
            text = fixture(name)
            minutes = '25' if code == '99213' else '45'
            with self.subTest(name=name):
                proposal = run_engine(text, [(code, [f'Total time on the date of service: {minutes} minutes.'])])[code]
                self.assertEqual(proposal.status, 'ready')
                self.assertNotIn('separate_em', clarified(proposal))
                self.assertNotIn('em.same_day_procedure', warned(proposal))
                self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))

    def test_control_a_procedure_reports_title_still_opens_the_summary(self):
        for name in (H2_01, 'h2-01-endoscopy-report.txt'):  # h2-01 keeps reading both extents
            text = (GI3 / name).read_text(encoding='utf-8')
            with self.subTest(name=name):
                self.assertTrue(sections._report_titled(text))
                self.assertIn(('procedure', 'procedure summary'), kinds(text))
                self.assertEqual(finding(text, 'gi.egd'), ('performed', 'third part of duodenum'))
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'terminal ileum'))
        template = (BANNER + 'Harrowgate Endoscopy Unit (fictional)\n{title}\nDate of procedure: 2026-10-20\nIndications\n'
                    '{indication}\nProcedure summary\nExamination | Instrument | Furthest point reached\nColonoscopy | '
                    'Adult colonoscope | Cecum\nImpression\nNormal colonoscopy.\n')
        for title in ('Colonoscopy report', 'COLONOSCOPY REPORT', 'Combined upper and lower endoscopy report',
                      'Bidirectional Endoscopy Report', 'Colonoscopy Procedure Note', 'Procedure note', 'Operative report',
                      'Procedure report - colonoscopy', 'PROCEDURE NOTE: COLONOSCOPY WITH BIOPSY',
                      'Outpatient Endoscopy Unit - Colonoscopy Report', '**Colonoscopy report** (amended)',
                      'Colonoscopy Report - Surveillance'):
            with self.subTest(title=title):
                text = template.format(title=title, indication='Surveillance of adenomas.')
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
        # the line above the label is not read for another occasion: a report's indication names earlier examinations
        text = template.format(title='Colonoscopy report', indication='Surveillance; a prior colonoscopy in 2019 removed '
                                                                      'two adenomas.')
        self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))

    def test_no_report_title_is_no_evidence(self):
        template = (BANNER + 'Harrowgate Endoscopy Unit (fictional)\n{title}Date of procedure: 2026-10-20\nIndications\n'
                    'Surveillance.\nProcedure summary\nExamination | Instrument | Furthest point reached\nColonoscopy | '
                    'Adult colonoscope | Cecum\nImpression\nNormal colonoscopy.\n')
        for title in OFFICE_TITLES + ('Pre-procedure note', 'Post-procedure note', 'Colonoscopy consultation note',
                                      'Prior colonoscopy report', 'Outside colonoscopy report', 'Pathology report',
                                      'Colonoscopy pathology report', 'Discharge summary', 'Nursing note', ''):
            with self.subTest(title=title):
                text = template.format(title=title + '\n' if title else '')
                self.assertFalse(sections._report_titled(text))
                self.assertNotIn(('procedure', 'procedure summary'), kinds(text))
                self.assertIsNone(finding(text, 'gi.colonoscopy')[1])  # the table's extent is never read
                if 'colonoscopy' not in title.lower():  # a title naming the service opens its own section (as installed)
                    self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))

    def test_the_title_is_the_heads_first_title_shaped_line(self):
        self.assertIsNone(sections._report_title('Harrowgate Endoscopy Unit'))  # no title shape: read on
        self.assertIsNone(sections._report_title('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'))
        self.assertIsNone(sections._report_title('Examination | Instrument | Furthest point reached'))
        self.assertTrue(sections._report_title('Upper endoscopy report'))
        self.assertFalse(sections._report_title('Progress Note'))
        self.assertFalse(sections._report_title('Progress Note - GI'))
        self.assertFalse(sections._report_title('Clinic note - return visit'))
        self.assertTrue(sections._report_title('Colonoscopy Report - Surveillance'))
        self.assertTrue(sections._report_title('PROCEDURE SUMMARY - DOUBLE-BALLOON ENTEROSCOPY'))
        self.assertFalse(sections._report_title('Note: colonoscopy findings were reviewed with the patient'))
        self.assertFalse(sections._report_title('Procedure report - see below'))
        # an office note whose head also holds a pasted report's title further down is the office note's
        text = fixture('a4-soap').replace('\nPatient: ', '\nColonoscopy report\nPatient: ')
        self.assertFalse(sections._report_titled(text))
        self.assertNotIn(('procedure', 'procedure summary'), kinds(text))


# --- EXT-4: a finding's or an act's column answers itself -----------------------------------------------------------------

class FindingColumnTests(unittest.TestCase):
    """sections._column_sense: a column speaks for the row only when the row's own service is its subject."""

    def test_ext4_the_reviewers_reports_are_ready(self):
        advance = 'The colonoscope was advanced to the cecum, identified by the appendiceal orifice and the ileocecal valve.'
        for name in ('t3-polyps-seen', 't2-colon-retro'):
            text = fixture(name)
            with self.subTest(name=name):
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                self.assertEqual(run_engine(text, [('45378', [advance])])['45378'].status, 'ready')
        text = fixture('t1-landmark-in-label')
        self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
        passed = 'The gastroscope was passed under direct vision to the second portion of the duodenum.'
        self.assertEqual(run_engine(text, [('43235', [passed])])['43235'].status, 'ready')

    def test_ext4_every_finding_and_act_column(self):
        colon = fixture('t3-polyps-seen')
        self.assertEqual(colon.count(' | Polyps seen\n'), 1)
        for label in ('Polyps seen', 'Lesions visualized', 'Bleeding seen', 'Retroflexion in rectum', 'Biopsy performed'):
            with self.subTest(label=label):
                self.assertEqual(sections._column_sense(sections.normalize_label(label)), sections.COLUMN_OWN)
                text = colon.replace(' | Polyps seen\n', f' | {label}\n')
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
        egd = fixture('t1-landmark-in-label')
        self.assertEqual(egd.count(' | Antrum biopsy\n'), 1)
        for label in ('Antrum biopsy', 'Duodenum biopsies', 'Biopsies (stomach)', 'Retroflexion in stomach',
                      'Esophagus biopsies'):
            with self.subTest(label=label):
                text = egd.replace(' | Antrum biopsy\n', f' | {label}\n')
                self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))

    def test_control_the_rows_own_reach_status_or_extent_still_speaks_for_it(self):
        for label in ('furthest point reached', 'extent', 'performed', 'procedure completed', 'colonoscopy performed',
                      'status', 'seen', 'done today'):
            with self.subTest(label=label):
                self.assertEqual(sections._column_sense(label), sections.COLUMN_ROW)
        # gi3 fix round 2 (X6): a landmark's reach is that landmark's (COLUMN_LANDMARK); it holds the row only where it
        # leaves unaffirmed a reach the row's own extent covers (the "Cecum reached | No" check below)
        for label in ('cecum reached', 'terminal ileum intubated', 'terminal ileum'):
            with self.subTest(label=label):
                self.assertEqual(sections._column_sense(label), sections.COLUMN_LANDMARK)
        for label in ('tissue sampled', 'complications', 'biopsies', 'instrument', 'comments', 'planned date'):
            with self.subTest(label=label):
                self.assertEqual(sections._column_sense(label), sections.COLUMN_OWN)
        # "Cecum reached | No" says the reach fell short: it keeps doubting the row's reach (asked, never the cecum)
        text = fixture('t3-polyps-seen').replace('Furthest point reached | Polyps seen\n', 'Furthest point reached | '
                                                 'Cecum reached\n')
        self.assertNotEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))


# --- EXT-5: a cited row never takes the answers of its own columns --------------------------------------------------------

class CitedRowTests(unittest.TestCase):
    """detect._doubt reads no answer cell that answers its own column for a passage that spans the row."""

    def test_ext5_a_cited_row_with_act_answers(self):
        text = fixture('b1-header-acts')
        row = 'Colonoscopy | Cecum | No | No | No'
        self.assertEqual(sections.layout(text).answer_cells.__len__(), 3)
        status, cues_ = span_status(text, row)
        self.assertFalse(any(c.startswith(detect.DOUBT_PREFIX) for c in cues_), cues_)
        self.assertEqual(status, 'performed')
        self.assertEqual(run_engine(text, [('45378', [row])])['45378'].status, 'ready')

    def test_ext5_h2_01s_cited_colonoscopy_row(self):
        text = (GI3 / H2_01).read_text(encoding='utf-8')
        row = 'Colonoscopy | Adult colonoscope | Terminal ileum, about 6 cm beyond the ileocecal valve | No'
        self.assertFalse(any(c.startswith(detect.DOUBT_PREFIX) for c in span_status(text, row)[1]))
        self.assertEqual(run_engine(text, [('45378', [row])])['45378'].status, 'ready')

    def test_control_a_status_answer_in_the_row_still_doubts(self):
        text = fixture('b1-header-acts').replace('Examination | Furthest point reached | Biopsy | Polypectomy | Tattoo\n'
                                                 'Colonoscopy | Cecum | No | No | No',
                                                 'Examination | Furthest point reached | Performed | Tattoo\n'
                                                 'Colonoscopy | Cecum | No | No')
        self.assertNotEqual(span_status(text, 'Colonoscopy | Cecum | No | No')[0], 'performed')
        # the answer cell cited alone is still read (it is the whole passage)
        at = text.index('Colonoscopy | Cecum | No | No') + len('Colonoscopy | Cecum | No | ')
        self.assertIsInstance(status_for_span(text, at, at + 2, date(2026, 10, 20)), tuple)


# --- EXT-6: an occasion phrase is no post-modifier of today's act -----------------------------------------------------------

class PostModifierOccasionTests(unittest.TestCase):
    """cues._POST_MODIFIER_WORD: another occasion's or time's words end the post-modifier."""

    advance = 'The colonoscope was advanced to the cecum, identified by the appendiceal orifice and the ileocecal valve.'

    def test_ext6_the_reviewers_reports_are_ready(self):
        for name in ('p2-indication-neg', 'p1-indication-neg', 'p3-indication-neg'):
            text = fixture(name)
            with self.subTest(name=name):
                self.assertEqual(finding(text, 'gi.colonoscopy'), ('performed', 'cecum'))
                indication = routed(text).finding('gi.colonoscopy').mentions
                self.assertNotIn('negated', [m.status for m in indication])
                self.assertEqual(run_engine(text, [('45378', [self.advance])])['45378'].status, 'ready')

    def test_ext6_occasion_phrases_never_carry_the_denial(self):
        post = cues.NEGATED_POST[0][1]
        for tail in (' at the outside hospital was not performed', ' at age 50 was never performed',
                     ' in the last ten years was not performed', ' in 2019 was not performed',
                     ' at another facility was not performed', ' in the future is not recommended',
                     ' at the prior visit was not performed', ' in March was not performed'):
            with self.subTest(tail=tail):
                self.assertIsNone(post.search(tail))

    def test_control_a_place_or_an_object_still_carries_it(self):
        post = cues.NEGATED_POST[0][1]
        for tail in (' of the channel was not attempted', ' of the cecum were not obtained', ' at the bedside was not performed',
                     ' across the stricture was not attempted', ' through the stenosis was not attempted'):
            with self.subTest(tail=tail):
                self.assertIsNotNone(post.search(tail))
        h204 = (GI3 / 'h2-04__3af9d4ce__2026-10-29.txt').read_text(encoding='utf-8')
        egd = routed(h204).finding('gi.egd')
        self.assertNotIn('dilation', next((f.value for f in egd.facts if f.name == 'interventions'), None) or '')


# --- EXT-7: a not-done status column reads with the opposite sense ----------------------------------------------------------

class NotDoneColumnTests(unittest.TestCase):
    """sections._column_sense COLUMN_NOT_DONE: "No" answers itself; anything else holds the row."""

    def test_ext7_the_reviewers_report(self):
        text = fixture('n1-cancelled-col')
        self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        self.assertIn(('other', sections.TABLE_ROW_HELD_LABEL), kinds(text))
        row = 'Colonoscopy | Adult colonoscope | - | Yes'
        self.assertEqual(span_status(text, row), ('uncertain', (detect.HELD_BY_A_NOT_DONE_COLUMN,)))
        passed = 'The gastroscope was passed under direct vision to the second portion of the duodenum.'
        proposals = run_engine(text, [('43239', [passed]), ('45378', [row])])
        self.assertEqual(proposals['43239'].status, 'ready')
        self.assertEqual(proposals['45378'].status, 'needs_clarification')

    def test_ext7_every_answer_but_no_holds_the_row(self):
        base = fixture('n1-cancelled-col')
        self.assertEqual(base.count('Colonoscopy | Adult colonoscope | - | Yes'), 1)
        for answer in ('Yes', 'Y', '-', '', 'Yes, inadequate preparation'):
            with self.subTest(answer=answer):
                text = base.replace('Colonoscopy | Adult colonoscope | - | Yes', f'Colonoscopy | Adult colonoscope | - | '
                                                                                f'{answer}')
                self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        for label in ('Aborted', 'Not performed', 'Incomplete', 'Postponed'):
            with self.subTest(label=label):
                text = base.replace('| Cancelled\n', f'| {label}\n')
                self.assertEqual(sections._column_sense(sections.normalize_label(label)), sections.COLUMN_NOT_DONE)
                self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
                self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))

    def test_ext7_a_cancelled_row_under_a_procedures_heading_is_held_too(self):
        text = (BANNER + 'Northgate Endoscopy (fictional)\nBidirectional Endoscopy Report\nDate of procedure: 2026-10-20\n'
                'Procedures performed\nExamination | Extent | Cancelled\nUpper endoscopy (EGD) | Second portion of the '
                'duodenum | No\nColonoscopy | - | Yes\nImpression\nSee above.\n')
        self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))

    def test_ext7_a_negation_turns_the_sense_and_a_two_valued_status_speaks_as_written(self):
        # gi3 fix round 2 (X3): a negated reach is the landmark's (COLUMN_LANDMARK), never a not-done status of the service
        for label, sense in (('not performed', sections.COLUMN_NOT_DONE), ('cecum not reached', sections.COLUMN_LANDMARK),
                             ('never performed', sections.COLUMN_NOT_DONE), ('not cancelled', sections.COLUMN_ROW),
                             ('status (completed/cancelled)', sections.COLUMN_ROW), ('completed (y/n)', sections.COLUMN_ROW),
                             ('biopsy (yes/no)', sections.COLUMN_OWN), ('no', sections.COLUMN_OWN), ('#', sections.COLUMN_OWN)):
            with self.subTest(label=label):
                self.assertEqual(sections._column_sense(label), sense)
        base = fixture('n1-cancelled-col')
        # "Completed (Y/N) | No": the answer stays with the row and doubts it (never cut into a clean reading)
        text = base.replace('| Cancelled\n', '| Completed (Y/N)\n').replace('| - | Yes', '| - | No')
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        # a two-valued status column names the status itself: "Completed" reads with its row, "Cancelled" cancels it
        text = base.replace('| Cancelled\n', '| Status (completed/cancelled)\n').replace(
            'Second portion of the duodenum | No', 'Second portion of the duodenum | Completed').replace('| - | Yes',
                                                                                                    '| - | Cancelled')
        self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        self.assertNotIn(('other', sections.TABLE_ROW_HELD_LABEL), kinds(text))

    def test_control_a_performed_column_reads_as_before(self):
        text = fixture('n1-cancelled-col').replace('| Cancelled\n', '| Performed\n').replace(
            'Second portion of the duodenum | No', 'Second portion of the duodenum | Yes').replace('| - | Yes', '| - | No')
        self.assertEqual(finding(text, 'gi.egd'), ('performed', 'second part of duodenum'))
        self.assertNotIn(finding(text, 'gi.colonoscopy')[0], ('performed', 'incomplete'))
        self.assertNotIn(('other', sections.TABLE_ROW_HELD_LABEL), kinds(text))


# --- EXT-2 (routing's half): a relative clause's denial is its head noun's ----------------------------------------------------

class RelativeClauseTests(unittest.TestCase):
    """detect._relative_denial; the inventory's half (services.read_clause) is the inventory owner's."""

    sentences = {'rel-r1': 'Biopsy of the polyp that was not removed was performed with cold forceps',
                 'rel-r2': 'Biopsies were taken with cold forceps from the polyp that was not removed',
                 'rel-r3': 'The polyp that was not removed was biopsied with cold forceps'}

    def test_ext2_routing_reads_the_biopsy_performed(self):
        for name, sentence in self.sentences.items():
            text = fixture(name)
            with self.subTest(name=name):
                status, cues_ = span_status(text, sentence)
                self.assertEqual(status, 'performed', cues_)
                self.assertNotEqual(run_engine(text, [('45380', [sentence])])['45380'].status, 'excluded')

    def test_ext2_the_removal_never_reaches_across_another_predicate(self):
        removal = next(p for name, p, _ in cues.INTERVENTIONS if name == 'cold forceps')
        self.assertIsNone(removal.search('the polyp that was not removed was performed with cold forceps'))
        self.assertIsNone(removal.search('the polyp that was not removed was biopsied with cold forceps'))
        self.assertIsNotNone(removal.search('the polyp was removed en bloc with cold forceps'))
        self.assertIsNotNone(removal.search('two polyps were removed with the cold forceps'))

    def test_control_a_denial_of_the_named_service_or_act_stays(self):
        report = fixture('rel-r2')
        sentence = self.sentences['rel-r2'] + '.'
        for denial in ('Biopsy of the polyp was not performed.', 'The lesion, which was not biopsied, was tattooed.',
                       'No biopsies were taken from the polyp that was left in place.'):
            text = report.replace(sentence, denial)
            with self.subTest(denial=denial):
                self.assertNotEqual(span_status(text, denial.rstrip('.'))[0], 'performed')
        visit = (BANNER + 'Saltmarsh Valley Gastroenterology (fictional)\nOffice visit\nDate of service: 2026-10-21\n'
                 'Office visit to review the colonoscopy, which was not performed.\n')
        self.assertEqual(span_status(visit, 'the colonoscopy, which was not performed')[0], 'negated')


# --- cost-1: blank runs read once ---------------------------------------------------------------------------------------------

class CostTests(unittest.TestCase):
    """sections._TABLE_ANSWER_CELL and _SEC_NO_ANSWER (stage limits: a member's context request 15 s)."""

    def timed(self, pattern, text):
        start = time.process_time()
        pattern.fullmatch(text)
        return time.process_time() - start

    def test_cost1_an_answer_cell_with_a_long_blank_run(self):
        # sizes a quadratic reading fails at once (plain runs: 0.5 s at 10,000 blanks and 1.9 s at 20,000, 48 s per stage
        # at the reviewer's 100,000-character paste); read once, each takes well under a millisecond
        for pattern, lead in ((sections._TABLE_ANSWER_CELL, 'no'), (sections._SEC_NO_ANSWER, ' no')):
            with self.subTest(pattern=pattern.pattern):
                small = self.timed(pattern, lead + ' ' * 10_000 + 'x')
                large = self.timed(pattern, lead + ' ' * 20_000 + 'x')
                self.assertLess(large, 0.25)
                self.assertLess(large, 3 * small + 0.02)

    def test_cost1_the_one_row_table_lays_out_in_time(self):
        text = BANNER + 'Item | Note | Other\nx | no' + ' ' * 20_000 + 'x | y\n'
        sections.layout.cache_clear()
        start = time.process_time()
        sections.layout(text)
        self.assertLess(time.process_time() - start, 0.5)  # plain runs: 1.9 s here; the reviewer's n/2 input 190 s
        sections.layout.cache_clear()

    def test_control_the_answers_still_match(self):
        for cell in ('No', ' no ', 'No.', 'N/A', 'not  applicable', '-', ' \u2014 ', 'none .  '):
            with self.subTest(cell=cell):
                self.assertIsNotNone(sections._TABLE_ANSWER_CELL.fullmatch(cell))
        for cell in ('no x', 'Not done', 'yes, biopsied', 'nothing'):
            with self.subTest(cell=cell):
                self.assertIsNone(sections._TABLE_ANSWER_CELL.fullmatch(cell))
        for value in (' none', ' N/A.', ' not applicable ', ' no'):
            with self.subTest(value=value):
                self.assertIsNotNone(sections._SEC_NO_ANSWER.fullmatch(value))


if __name__ == '__main__':
    unittest.main()
