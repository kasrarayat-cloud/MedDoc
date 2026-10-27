"""Repair round 7c8, cluster FORMATS: what the skeptic of round ec5's FORMATS repair demonstrated (sk:1 to sk:11). The
PDF, OCR and Word readings of the owner's historical findings read what the text reads. Synthetic text only: every
document opens with the synthetic banner.

Each PDF test writes its input through the real PDF writer (tests.support.docgen.make_pdf) and reads it back with the
real extraction (extract_document), as the pipeline does, then reads it as the engine does: routing over the canonical
text, the documented-service reader over the same text with the revision's page spans.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import cues, detect, services
from studio.ingest.extract import extract_document
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess
from tests.support import docgen

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'


def pdf(*pages: str):
    """The pages (each already laid out in lines) as a digital PDF, read back by the real extraction."""
    result = extract_document(docgen.make_pdf(list(pages)), 'synthetic.pdf', 'application/pdf')
    assert result.status == 'ok', result.messages
    return result.text, result.pages


def run(text: str, codes=(), pages=()):
    """The assessment the engine makes for ``text`` with the provider selecting ``codes`` [(code, quoted passage)]."""
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    selected = []
    for code, quote in codes:
        at = text.index(quote)
        selected.append(ProviderCode('selected', 'cpt', code, 'synthetic', (EvidenceSpan(0, at, at + len(quote), quote,
                                                                                        True),)))
    routing = detect.route(text, day)
    result = assess(text=text, pages=tuple(pages), context=facts, routing=routing,
                    normalized=NormalizedResponse('replay', 'synthetic@1', tuple(selected)),
                    reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')
    return result, routing


def services_of(result):
    return [(s['family'], s['status'], s['completion']) for s in result.services['services']]


def acts_of(result, kind=None):
    return [(a['kind'], a['status']) for s in result.services['services'] for a in s['acts']
            if kind is None or a['kind'] == kind]


def proposals_of(result):
    return {p.code: (p.status, sorted(c.id for c in p.checks if c.status in ('warn', 'fail'))) for p in result.proposals}


def unresolved_of(result):
    return [(u['family'], u.get('act', ''), u['reason']) for u in result.completeness['unresolved_items']]


class PageFurnitureAtAPageJoinTests(SimpleTestCase):
    """sk:1 (formats-6), sk:2 (formats-5 b) and sk:3 (formats-2): a running header or footer at a page join ("Page 1
    of 2", a repeated letterhead, "Confidential") stood between the two halves of a sentence, so the join paired the
    furniture line, not the sentence, and the sentence read as two: a complete colonoscopy read incomplete with a 52/53
    consideration (the Elena 45385 class), a performed EGD went unread with coding complete, a 2020 snare read as
    today's and a snare the note says was not done read READY. A page's furniture is skipped when the join is decided,
    and never read into the sentence; routing's stop cue reads a negation across it too."""

    PAGE_1 = (f'{BANNER}\nSCREENING COLONOSCOPY\nDate of service: 2026-10-26\nProcedure: Colonoscopy.\n'
              'The colonoscope was advanced to the cecum. The procedure was not')
    PAGE_2 = 'discontinued; it was completed without interruption.'
    CITE = [('45378', 'SCREENING COLONOSCOPY')]

    def assert_complete(self, text, pages):
        result, routing = run(text, self.CITE, pages)
        self.assertEqual([(f.family, f.status) for f in routing.findings], [('gi.colonoscopy', 'performed')])
        self.assertEqual(services_of(result), [('gi.colonoscopy', 'performed', 'complete')])
        self.assertEqual(proposals_of(result)['45378'], ('ready', []))
        self.assertEqual([m for p in result.proposals for m in p.modifier_considerations], [])

    def test_the_one_page_control(self):
        self.assert_complete(*pdf(self.PAGE_1 + '\n' + self.PAGE_2))

    def test_a_running_footer_or_header_between_not_and_discontinued(self):
        for label, pages in (('footer Page 1 of 2', (self.PAGE_1 + '\nPage 1 of 2', self.PAGE_2)),
                             ('header Page 2 of 2', (self.PAGE_1, 'Page 2 of 2\n' + self.PAGE_2)),
                             ('the letterhead repeated atop page 2', (self.PAGE_1, BANNER + '\n' + self.PAGE_2)),
                             ('footer and header', (self.PAGE_1 + '\nPage 1 of 2', 'Page 2 of 2\n' + self.PAGE_2)),
                             ('footer 1', (self.PAGE_1 + '\n1', self.PAGE_2)),
                             ('footer - 1 -', (self.PAGE_1 + '\n- 1 -', self.PAGE_2)),
                             ('footer Page 1', (self.PAGE_1 + '\nPage 1', self.PAGE_2)),
                             ('footer Confidential', (self.PAGE_1 + '\nConfidential', self.PAGE_2)),
                             ('footer Printed', (self.PAGE_1 + '\nPrinted 10/27/2026 09:14', self.PAGE_2)),
                             ('header facility', (self.PAGE_1, 'Halcyon Valley Hospital (fictional) - Gastroenterology\n'
                                                  + self.PAGE_2)),
                             ('header 2', (self.PAGE_1, '2\n' + self.PAGE_2))):
            with self.subTest(label):
                self.assert_complete(*pdf(*pages))

    def test_a_running_title_that_names_the_service_never_reads_it_incomplete(self):
        # "SCREENING COLONOSCOPY (continued)" atop page 2: routing reads the header's own words ('continued' after the
        # service name) and holds the family - an over-hold, never the incomplete reading and its 52/53 consideration
        text, pages = pdf(self.PAGE_1, 'SCREENING COLONOSCOPY (continued)\n' + self.PAGE_2)
        result, routing = run(text, self.CITE, pages)
        self.assertNotIn('incomplete', [f.status for f in routing.findings])
        self.assertNotIn('incomplete', [s[1] for s in services_of(result)])
        self.assertNotIn('service.incomplete', proposals_of(result)['45378'][1])
        self.assertEqual([m for p in result.proposals for m in p.modifier_considerations], [])

    def test_never_terminated_and_halted_across_the_furniture(self):
        for page_1, page_2 in ((self.PAGE_1.replace('was not', 'was never') + '\nPage 1 of 2', self.PAGE_2),
                               (self.PAGE_1 + '\nPage 1 of 2', self.PAGE_2.replace('discontinued', 'terminated')),
                               (self.PAGE_1, 'Page 2 of 2\n' + self.PAGE_2.replace('discontinued', 'halted'))):
            with self.subTest(page_2=page_2[:30]):
                self.assert_complete(*pdf(page_1, page_2))

    def test_the_furniture_is_never_read_into_the_sentence(self):
        for furniture in ('Page 2 of 2', BANNER):
            with self.subTest(furniture):
                text, pages = pdf(self.PAGE_1, furniture + '\n' + self.PAGE_2)
                flow = services.reflow(text, pages)
                self.assertEqual(len(flow), len(text))
                at = text.index('was not') + len('was not')
                self.assertEqual(flow[at:text.index('discontinued')].strip(), '')  # the furniture is blanked
                self.assertNotIn(furniture, flow[text.index('Procedure: Colonoscopy.'):])

    def test_a_real_stop_after_a_finished_page_stays_a_stop(self):  # control (must not change)
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\nThe colonoscope was advanced to the '
                  'splenic flexure; the cecum was not reached.\nPage 1 of 2')
        page_2 = 'Page 2 of 2\nThe procedure was discontinued because of poor preparation.'
        text, pages = pdf(page_1, page_2)
        result, routing = run(text, [('45378', 'COLONOSCOPY REPORT')], pages)
        self.assertEqual([(f.family, f.status) for f in routing.findings], [('gi.colonoscopy', 'incomplete')])
        self.assertEqual(services_of(result), [('gi.colonoscopy', 'incomplete', 'incomplete')])

    def test_a_heading_after_a_finished_sentence_is_no_furniture(self):  # control (must not change)
        # page 1 ends with a finished sentence and page 2 opens with a section heading over a lower-case line: the
        # heading is the document's, never skipped as furniture
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\nThe colonoscope was advanced to the '
                  'cecum and the examination was complete.')
        page_2 = 'FINDINGS\nrandom biopsies were taken from the right and left colon.'
        text, pages = pdf(page_1, page_2)
        self.assertIn('FINDINGS', services.reflow(text, pages))

    def test_an_instrument_and_its_predicate_across_the_furniture(self):
        # sk:2, formats-5 (b): the performed EGD went unread and coding read complete
        page_1 = (f'{BANNER}\nOPERATIVE NOTE\nDate of service: 2026-10-14\nWith the patient in the left lateral '
                  'position the gastroscope was')
        page_2 = 'inserted transorally and advanced to the second portion of the duodenum.\nThe examination was normal.'
        for pages in ((page_1 + '\n' + page_2,), (page_1 + '\nPage 1 of 2', page_2), (page_1, 'Page 2 of 2\n' + page_2)):
            with self.subTest(pages=pages[-1][:12]):
                text, spans = pdf(*pages)
                result = run(text, (), spans)[0]
                self.assertEqual(services_of(result), [('gi.egd', 'performed', 'complete')])
                self.assertEqual(unresolved_of(result), [('gi.egd', '', 'no_proposal')])
                self.assertEqual(result.completeness['state'], 'incomplete')

    def test_a_dated_history_sentence_across_the_furniture_stays_history(self):
        # sk:3, formats-2 (a): the 2020 snare read as today's (45378 held as base_included, the snare unresolved)
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-08\nPlace of service: Ambulatory surgery '
                  'center\nINDICATION: Surveillance. At colonoscopy on 2020-04-14 a single 5 mm tubular adenoma was')
        page_2 = ('removed with a cold snare.\n\nPROCEDURE\nThe colonoscope was advanced to the cecum and the examination '
                  'was complete. No polyps were\nseen.')
        quote = 'The colonoscope was advanced to the cecum and the examination was complete.'
        for pages in ((page_1 + '\n' + page_2,), (page_1 + '\nPage 1 of 2', page_2), (page_1, 'Page 2 of 2\n' + page_2)):
            with self.subTest(pages=pages[-1][:12]):
                text, spans = pdf(*pages)
                result = run(text, [('45378', quote)], spans)[0]
                self.assertEqual(acts_of(result, 'snare'), [('snare', 'historical')])
                self.assertEqual(proposals_of(result)['45378'], ('ready', []))
                self.assertEqual(unresolved_of(result), [])

    def test_a_denial_across_the_furniture_is_never_ready(self):
        # sk:3, formats-2 (b, V3b): a snare the note says was not done read performed and 45385 READY
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-08\nThe colonoscope was advanced to the '
                  'cecum.\nFINDINGS: In the distal sigmoid colon there was an 8 mm sessile polyp. The polyp was not')
        page_2 = 'removed with a cold snare because the patient had taken clopidogrel that morning.'
        for pages in ((page_1 + '\nPage 1 of 2', page_2), (page_1, 'Page 2 of 2\n' + page_2)):
            with self.subTest(pages=pages[-1][:12]):
                text, spans = pdf(*pages)
                result = run(text, [('45385', 'removed with a cold snare')], spans)[0]
                self.assertEqual(acts_of(result, 'snare'), [('snare', 'negated')])
                self.assertNotEqual(proposals_of(result)['45385'][0], 'ready')


class RoutingStopAcrossFurnitureTests(SimpleTestCase):
    """sk:1, routing's half: the stop cue's negation is read across a page's furniture only where a page join leaves
    it (a blank line among the whitespace), and a line written as a heading only before a stop word that goes on in
    lower case."""

    def status(self, text):
        return [(f.family, f.status) for f in detect.route(text, date(2026, 10, 26)).findings]

    HEAD = f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\nThe colonoscope was advanced to the cecum. '

    def test_a_heading_before_a_capitalised_stop_is_no_furniture(self):  # control
        text = self.HEAD + 'The scope was not\n\nIMPRESSION\nDiscontinued at the splenic flexure because of looping.\n'
        self.assertEqual(self.status(text), [('gi.colonoscopy', 'incomplete')])

    def test_furniture_without_a_page_join_is_read_as_written(self):  # control
        text = self.HEAD + 'The procedure was not\nPage 1 of 2\ndiscontinued; it was completed.\n'
        self.assertEqual(self.status(text), [('gi.colonoscopy', 'incomplete')])

    def test_the_shapes(self):
        for line in ('Page 1 of 2', '- 1 -', '2', 'Page 1', 'p. 3', '1/2'):
            with self.subTest(line):
                self.assertTrue(cues.page_number_line(line))
        for line in ('Confidential', 'Printed 10/27/2026 09:14', BANNER, 'SCREENING COLONOSCOPY (continued)'):
            with self.subTest(line):
                self.assertTrue(cues.heading_shaped_line(line))
        for line in ('FINDINGS:', 'The procedure was not', 'biopsies were taken', 'Page 1 of 2 of the report was lost.'):
            with self.subTest(line):
                self.assertFalse(cues.page_number_line(line) or cues.heading_shaped_line(line))

