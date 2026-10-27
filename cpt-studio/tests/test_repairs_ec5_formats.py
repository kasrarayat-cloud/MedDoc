"""Repair round ec5, cluster FORMATS: the PDF (and OCR) readings of the owner's historical findings read what the text
reads (refutation r1, formats-0 to formats-7). Synthetic text only: every document opens with the synthetic banner.

Each test writes the finding's smallest input through the real PDF writer (tests.support.docgen.make_pdf) and reads it
back with the real extraction (extract_document), as the pipeline does, then reads it as the engine does: routing over
the canonical text, the documented-service reader over the same text with the revision's page spans.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.ingest.extract import extract_document
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
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


class PageJoinInsideASentenceTests(SimpleTestCase):
    """formats-6: a page boundary inside "The procedure was not / discontinued; it was completed" read a complete
    colonoscopy as incomplete (a warning and a 52/53 consideration: the Elena 45385 class). A page join is the line
    break it replaces: inside a sentence it is a soft wrap, for routing's stop cue and for the reader."""

    PAGE_1 = (f'{BANNER}\nSCREENING COLONOSCOPY\nDate of service: 2026-10-26\nProcedure: Colonoscopy.\n'
              'The colonoscope was advanced to the cecum. The procedure was not')
    PAGE_2 = 'discontinued; it was completed without interruption.'

    def assert_complete(self, text, pages, code='45378', cite='SCREENING COLONOSCOPY', family='gi.colonoscopy',
                        completion='complete'):
        result, routing = run(text, [(code, cite)], pages)
        self.assertEqual([(f.family, f.status) for f in routing.findings], [(family, 'performed')])
        self.assertEqual(services_of(result), [(family, 'performed', completion)])
        self.assertEqual(proposals_of(result)[code], ('ready', []))
        self.assertEqual([m for p in result.proposals for m in p.modifier_considerations], [])

    def test_a_page_join_between_not_and_discontinued_reads_a_complete_colonoscopy(self):
        one_text, one_pages = pdf(self.PAGE_1 + '\n' + self.PAGE_2)
        self.assert_complete(one_text, one_pages)  # control: the same words on one page
        text, pages = pdf(self.PAGE_1, self.PAGE_2)
        self.assertIn('was not\n\n\ndiscontinued', text)  # the page join the extraction writes
        self.assert_complete(text, pages)

    def test_a_wide_gap_on_one_line_is_still_not_discontinued(self):
        text = self.PAGE_1 + '   ' + self.PAGE_2 + '\n'
        self.assert_complete(text, ())

    def test_a_family_without_an_endpoint_reads_the_join_as_the_reader_alone(self):
        page_1 = (f'{BANNER}\nFLEXIBLE SIGMOIDOSCOPY REPORT\nDate of service: 2026-10-26\n'
                  'The sigmoidoscope was advanced to 60 cm in the descending colon. The procedure was not')
        text, pages = pdf(page_1, self.PAGE_2)
        self.assert_complete(text, pages, code='45330', cite='FLEXIBLE SIGMOIDOSCOPY REPORT', family='gi.flex_sig',
                             completion='unknown')

    def test_a_page_join_between_no_and_biopsies_reads_as_on_one_page(self):
        page_1 = (f'{BANNER}\nSCREENING COLONOSCOPY\nDate of service: 2026-10-26\nThe colonoscope was advanced to the '
                  'cecum. The examination was complete. No polyps were found, and no')
        page_2 = 'biopsies were taken. Withdrawal time was 9 minutes.'
        codes = [('45378', 'SCREENING COLONOSCOPY'), ('45380', 'biopsies were taken')]
        one_text, one_pages = pdf(page_1 + '\n' + page_2)
        one = run(one_text, codes, one_pages)[0]
        text, pages = pdf(page_1, page_2)
        two = run(text, codes, pages)[0]
        self.assertEqual(acts_of(one, 'biopsy'), [('biopsy', 'negated')])
        self.assertEqual(acts_of(two, 'biopsy'), acts_of(one, 'biopsy'))
        # Routing, which has no page spans, still reads the join as a paragraph break and the biopsy as done: the two
        # readers disagree, so the code the one-page reading excludes is held - never ready, never newly excluded.
        self.assertEqual(proposals_of(one)['45380'][0], 'excluded')
        self.assertEqual(proposals_of(two)['45380'][0], 'needs_clarification')

    def test_a_real_stop_across_a_page_join_stays_a_stop(self):
        # control: a finished sentence ends page 1; page 2 says the procedure was discontinued
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\nThe colonoscope was advanced to the '
                  'splenic flexure; the cecum was not reached.')
        page_2 = 'The procedure was discontinued because of poor preparation.'
        text, pages = pdf(page_1, page_2)
        result, routing = run(text, [('45378', 'COLONOSCOPY REPORT')], pages)
        self.assertEqual([(f.family, f.status) for f in routing.findings], [('gi.colonoscopy', 'incomplete')])
        self.assertEqual(services_of(result), [('gi.colonoscopy', 'incomplete', 'incomplete')])

    def test_a_typed_blank_line_is_never_a_page_join(self):
        # the same two lines in a text file, with a blank line typed between them: no page spans, so no join
        text = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\n'
                'At colonoscopy on 2020-04-14 a single 5 mm tubular adenoma was\n\nremoved with a cold snare.\n')
        self.assertEqual(services.reflow(text), text)
        spans = (PageSpan(1, 0, text.index('\n\nremoved') + 1), PageSpan(2, text.index('removed'), len(text)))
        self.assertNotEqual(services.reflow(text, spans), text)  # the same gap as a recorded page join is joined
