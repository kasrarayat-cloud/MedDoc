"""Refutation r1 repairs, cluster S: document structure - parts, sections, headings and the service date.

Each text is a synthetic, fictional paraphrase written for the case under test; the expected readings are written here,
outside the reader. None of them is a sentence the reader matches by its exact wording.
"""
import types
from datetime import date

from django.test import SimpleTestCase

from studio import jobs
from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = date(2026, 10, 14)


def engine(text, picks, day=DAY):
    """The engine's result for provider-selected (code, quote) picks against an empty reference."""
    codes = []
    for code, quote in picks:
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),)))
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def statuses(result):
    return {p.code: (p.bucket, p.status) for p in result.proposals}


def unresolved(result):
    return sorted((u.get('family'), u.get('act') or '', u.get('reason'), bool(u.get('second_review')))
                  for u in (result.completeness or {}).get('unresolved_items', []))


def second_review(result):
    """The items a second review would be paid for (jobs._second_review_items reads the assessment)."""
    items, _ = jobs._second_review_items(types.SimpleNamespace(completeness=result.completeness,
                                                               services=result.services))
    return items


def inventory(text, day=DAY):
    facts = gi_context.extract_context(text)
    return services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)


def acts(inv, family, status='performed'):
    return sorted(a.kind for s in inv.services if s.family == family for a in s.acts if a.status == status)


def performed(inv, family):
    return [s for s in inv.services if s.family == family and s.status in services.POSITIVE_STATUSES]


def heading_titles(text, day=DAY):
    """The headings the reader opens a service's part with (their title passages)."""
    return [p.title.text for p in services.parts(text, service_date=day) if p.title is not None]


# --- boxes-4: a heading that carries the service's own attributes is that service's heading -------------------------

TWO_SERVICES = (HEAD + 'PROCEDURE REPORT\nDate of service: 10/14/2026\nProcedures: EGD and colonoscopy\n{egd}\n'
                'The endoscope was advanced to the second portion of the duodenum and the examination was completed. Two '
                'biopsies were taken with cold forceps.\n{colon}\nThe colonoscope was advanced to the cecum and the '
                'examination was completed. A 5 mm polyp was removed with a cold snare.\nImpression: Gastritis. Colon '
                'polyp.\n')
TWO_PICKS = [('43235', 'The endoscope was advanced to the second portion of the duodenum'),
             ('45378', 'The colonoscope was advanced to the cecum')]


class QualifiedServiceHeadingTests(SimpleTestCase):
    """boxes-4 (high, a WIP 8 regression): a label line naming one service opened no heading when it carried any word
    outside the heading vocabulary ("EGD (diagnostic):", "Colonoscopy (screening):", "EGD performed:"), so in a report of
    two services the act sentences under them, with no anatomy of their own, were read for neither: both base codes
    went ready, the biopsy and the polypectomy were hidden and no second review was made. A heading that carries the
    service's own attributes - its intent, its performance, its extent, the service date - is that service's heading;
    so is one with any other qualifier when the procedure line lists the service. A heading that gives another time,
    asks, doubts, cancels or denies never is."""

    def assert_both_acts_read(self, egd, colon, text=None):
        text = text or TWO_SERVICES.format(egd=egd, colon=colon)
        inv = inventory(text)
        self.assertEqual(acts(inv, 'gi.egd'), ['biopsy'])
        self.assertEqual(acts(inv, 'gi.colonoscopy'), ['snare'])
        result = engine(text, TWO_PICKS)
        self.assertEqual(statuses(result), {'43235': ('selected', 'needs_clarification'),
                                            '45378': ('selected', 'needs_clarification')})
        self.assertEqual(unresolved(result), [('gi.colonoscopy', 'snare', 'not_covered', True),
                                              ('gi.egd', 'biopsy', 'not_covered', True)])
        self.assertEqual(len(second_review(result)), 2)

    def test_the_findings_headings(self):
        for egd, colon in (('EGD (diagnostic):', 'Colonoscopy (screening):'), ('EGD performed:', 'Colonoscopy performed:'),
                           ('Diagnostic EGD:', 'Screening colonoscopy:'),
                           ('Upper endoscopy (diagnostic):', 'Colonoscopy (surveillance):'),
                           ('EGD - diagnostic:', 'COLONOSCOPY (SCREENING):'), ('EGD:', 'Colonoscopy to the cecum:')):
            with self.subTest(egd=egd, colon=colon):
                self.assert_both_acts_read(egd, colon)

    def test_another_wording_and_position(self):
        text = (HEAD + 'Endoscopy report\nDate of service: 10/14/2026\nProcedures performed: upper endoscopy, colonoscopy\n'
                'Screening colonoscopy:\nThe colonoscope was passed to the cecum. A 7 mm sessile polyp was seen in the '
                'sigmoid colon. It was removed with a cold snare and retrieved.\nDiagnostic upper endoscopy:\nThe gastroscope '
                'was passed to the second part of the duodenum. Cold forceps biopsies were obtained.\n')
        inv = inventory(text)
        self.assertEqual(acts(inv, 'gi.colonoscopy'), ['snare'])
        self.assertEqual(acts(inv, 'gi.egd'), ['biopsy'])

    def test_without_a_procedure_line_or_a_title(self):
        # the services are documented by their instruments only: the heading's own words decide
        for egd, colon in (('EGD (diagnostic):', 'Colonoscopy (screening):'), ('Diagnostic EGD:', 'Surveillance colonoscopy:'),
                           ('EGD performed:', 'Colonoscopy to the cecum:'),
                           ('EGD (10/14/2026):', 'Colonoscopy (10/14/2026):')):
            text = (HEAD + 'Endoscopy unit\nDate of service: 10/14/2026\n' + egd + '\nThe gastroscope was advanced to the '
                    'second portion of the duodenum. Two biopsies were taken with cold forceps.\n' + colon + '\nThe '
                    'colonoscope was advanced to the cecum. A 5 mm polyp was removed with a cold snare.\n')
            with self.subTest(egd=egd, colon=colon):
                inv = inventory(text)
                self.assertEqual(acts(inv, 'gi.egd'), ['biopsy'])
                self.assertEqual(acts(inv, 'gi.colonoscopy'), ['snare'])

    def test_a_qualifier_no_list_knows_when_the_procedure_line_lists_the_service(self):
        self.assert_both_acts_read('EGD (with propofol):', 'Colonoscopy (with propofol):')
        self.assert_both_acts_read('EGD - outpatient unit 2:', 'Colonoscopy - outpatient unit 2:')

    def test_the_service_date_in_the_heading(self):
        self.assert_both_acts_read('EGD (10/14/2026):', 'Colonoscopy (10/14/2026):')

    def test_unqualified_headings_read_as_before(self):
        self.assert_both_acts_read('EGD:', 'Colonoscopy:')

    def test_a_heading_that_gives_another_time_or_asks_is_never_todays(self):
        # even in a report whose procedure line lists the colonoscopy, a label that asks or gives another time opens no
        # heading of today's colonoscopy
        for label in ('Colonoscopy within 10 years:', 'Last colonoscopy:', 'Colonoscopy up to date:',
                      'Colonoscopy since 2016:', 'Colonoscopy due:', 'Colonoscopy (2016):', 'Colonoscopy (2026):',
                      'Colonoscopy report (2023-05-02):', 'Next colonoscopy:', 'Colonoscopy (attempted):',
                      'Colonoscopy (cancelled):', 'Colonoscopy not done:'):
            text = TWO_SERVICES.format(egd='EGD:', colon='Colonoscopy:') + label + '\nYes\n'
            with self.subTest(label=label):
                self.assertNotIn(label, heading_titles(text))

    def test_an_office_note_question_opens_no_service(self):
        for label in ('Colonoscopy within 10 years:', 'Colonoscopy up to date:', 'Colonoscopy prep tolerance:',
                      'Colonoscopy (with propofol):'):
            text = (HEAD + 'Gastroenterology office visit\nDate of service: 10/14/2026\nEstablished patient office visit '
                    'for heartburn.\n' + label + '\nYes\nAssessment: GERD.\n')
            with self.subTest(label=label):
                self.assertNotIn(label, heading_titles(text))
                self.assertEqual(performed(inventory(text), 'gi.colonoscopy'), [])
