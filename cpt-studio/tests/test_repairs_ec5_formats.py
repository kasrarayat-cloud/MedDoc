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
from tests.support.dates import answered_context

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'


def pdf(*pages: str):
    """The pages (each already laid out in lines) as a digital PDF, read back by the real extraction."""
    result = extract_document(docgen.make_pdf(list(pages)), 'synthetic.pdf', 'application/pdf')
    assert result.status == 'ok', result.messages
    return result.text, result.pages


def run(text: str, codes=(), pages=()):
    """The assessment the engine makes for ``text`` with the provider selecting ``codes`` [(code, quoted passage)]."""
    # refutation phase 2 (P2DATES, rule 1): a PDF or Word text keeps no blank line, so its header block runs into the
    # body and its labelled date is asked; these tests read it with the member's answer (tests/support/dates.py)
    facts = answered_context(text)
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

    PAGE_1 = (f'{BANNER}\nSCREENING COLONOSCOPY\nDate of service: 2026-10-26\n\nProcedure: Colonoscopy.\n'
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
        page_1 = (f'{BANNER}\nFLEXIBLE SIGMOIDOSCOPY REPORT\nDate of service: 2026-10-26\n\n'
                  'The sigmoidoscope was advanced to 60 cm in the descending colon. The procedure was not')
        text, pages = pdf(page_1, self.PAGE_2)
        self.assert_complete(text, pages, code='45330', cite='FLEXIBLE SIGMOIDOSCOPY REPORT', family='gi.flex_sig',
                             completion='unknown')

    def test_a_page_join_between_no_and_biopsies_reads_as_on_one_page(self):
        page_1 = (f'{BANNER}\nSCREENING COLONOSCOPY\nDate of service: 2026-10-26\n\nThe colonoscope was advanced to the '
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
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\n\nThe colonoscope was advanced to the '
                  'splenic flexure; the cecum was not reached.')
        page_2 = 'The procedure was discontinued because of poor preparation.'
        text, pages = pdf(page_1, page_2)
        result, routing = run(text, [('45378', 'COLONOSCOPY REPORT')], pages)
        self.assertEqual([(f.family, f.status) for f in routing.findings], [('gi.colonoscopy', 'incomplete')])
        self.assertEqual(services_of(result), [('gi.colonoscopy', 'incomplete', 'incomplete')])

    def test_a_typed_blank_line_is_never_a_page_join(self):
        # the same two lines in a text file, with a blank line typed between them: no page spans, so no join
        text = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\n\n'
                'At colonoscopy on 2020-04-14 a single 5 mm tubular adenoma was\n\nremoved with a cold snare.\n')
        self.assertEqual(services.reflow(text), text)
        spans = (PageSpan(1, 0, text.index('\n\nremoved') + 1), PageSpan(2, text.index('removed'), len(text)))
        self.assertNotEqual(services.reflow(text, spans), text)  # the same gap as a recorded page join is joined

    def test_a_dated_history_sentence_across_a_page_join_stays_history(self):
        # formats-2: "At colonoscopy on 2020-04-14 a single 5 mm tubular adenoma was" / "removed with a cold snare." read
        # as today's snare (45378 held as base_included, the 2020 snare listed unresolved)
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-08\n\nPlace of service: Ambulatory surgery '
                  'center\nINDICATION: Surveillance. At colonoscopy on 2020-04-14 a single 5 mm tubular adenoma was')
        page_2 = ('removed with a cold snare.\n\nPROCEDURE\nThe colonoscope was advanced to the cecum and the examination '
                  'was complete. No polyps were\nseen.')
        quote = 'The colonoscope was advanced to the cecum and the examination was complete.'
        for text, pages in (pdf(page_1 + '\n' + page_2), pdf(page_1, page_2)):
            with self.subTest(pages=len(pages)):
                result = run(text, [('45378', quote)], pages)[0]
                self.assertEqual(acts_of(result, 'snare'), [('snare', 'historical')])
                self.assertEqual(proposals_of(result)['45378'], ('ready', []))
                self.assertEqual(result.completeness['unresolved_items'], [])

    def test_a_denial_across_a_page_join_is_read_as_a_denial(self):
        # formats-2 V3b: "The polyp was not" / "removed with a cold snare because ..." read as a performed snare
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-08\n\nThe colonoscope was advanced to the cecum.'
                  '\nFINDINGS: In the distal sigmoid colon there was an 8 mm sessile polyp. The polyp was not')
        page_2 = 'removed with a cold snare because the patient had taken clopidogrel that morning.'
        text, pages = pdf(page_1, page_2)
        result = run(text, [('45385', 'removed with a cold snare')], pages)[0]
        self.assertEqual(acts_of(result, 'snare'), [('snare', 'negated')])
        self.assertNotEqual(proposals_of(result)['45385'][0], 'ready')

    def test_an_instrument_and_its_predicate_across_a_page_join_document_the_service(self):
        # formats-5 (b): "... the gastroscope was" / "inserted transorally and advanced ..." read no EGD at all, so
        # coding read complete with a documented service missing
        page_1 = (f'{BANNER}\nOPERATIVE NOTE\nDate of service: 2026-10-14\n\nWith the patient in the left lateral position '
                  'the gastroscope was')
        page_2 = 'inserted transorally and advanced to the second portion of the duodenum.\nThe examination was normal.'
        for text, pages in (pdf(page_1 + '\n' + page_2), pdf(page_1, page_2)):
            with self.subTest(pages=len(pages)):
                result = run(text, (), pages)[0]
                self.assertEqual(services_of(result), [('gi.egd', 'performed', 'complete')])
                self.assertEqual([(u['family'], u['reason']) for u in result.completeness['unresolved_items']],
                                 [('gi.egd', 'no_proposal')])
                self.assertEqual(result.completeness['state'], 'incomplete')


class WrappedCheckBoxRowTests(SimpleTestCase):
    """formats-0 and formats-1: a check-box row is read over its logical extent. A PDF line that wraps a row's marked
    option ("[X] Not" / "performed"), its note ("[X] Not taken - not" / "sampled before resection") or its label ("...
    3 cm distal to the" / "site) [ ] Performed [X] Not performed") had dropped the nursing row's "Not performed" (the
    physician-vs-nursing tattoo conflict lost, 45381 READY: the Elena tattoo-conflict class) or read the note's tail as
    a performed act. The row continues on a next line that goes on in lower case with no mark of its own, or on a row
    line that opens with the lower-case tail of a label begun above; it never runs on into another row."""

    HEAD = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-14\n\n'
            'The colonoscope was advanced to the cecum. The examination was complete.\n'
            'The colon wall distal to the lesion was tattooed with carbon-particle ink.\nNURSING CHECKLIST\n')
    CITE = [('45381', 'The colon wall distal to the lesion was tattooed with carbon-particle ink.')]

    def read(self, rows: str):
        text, pages = pdf(self.HEAD + rows)
        return run(text, self.CITE, pages)[0]

    def assert_conflict(self, result):
        self.assertIn(('tattoo', 'negated'), acts_of(result, 'tattoo'))
        self.assertEqual([c['subject'] for c in result.services['conflicts']], ['tattoo'])
        status, _ = proposals_of(result)['45381']
        self.assertEqual(status, 'needs_clarification')
        self.assertIn('conflict:tattoo', [q.fact for p in result.proposals for q in p.clarifications])

    def test_the_unwrapped_row_keeps_its_conflict(self):  # control
        self.assert_conflict(self.read('Tattoo injection [ ] Performed [X] Not performed\n'))

    def test_a_marked_option_wrapped_onto_the_next_line(self):
        self.assert_conflict(self.read('Tattoo injection            [ ] Performed   [X] Not\nperformed\n'))

    def test_a_row_label_wrapped_onto_the_boxes_line(self):
        self.assert_conflict(self.read('Tattoo injection (carbon-particle ink, 3 cm distal to the\n'
                                       'site)   [ ] Performed   [X] Not performed\n'))

    def test_an_agreeing_row_leaves_the_code_ready(self):  # control
        result = self.read('Tattoo injection            [X] Performed   [ ] Not\nperformed\n')
        self.assertEqual(result.services['conflicts'], [])
        self.assertEqual(proposals_of(result)['45381'], ('ready', []))

    def test_two_rows_stay_two_rows(self):  # control: a row never runs on into the next row
        result = self.read('Tattoo injection [X] Performed [ ] Not performed\nBiopsy [ ] Performed [X] Not performed\n')
        self.assertEqual(acts_of(result, 'tattoo'), [('tattoo', 'performed'), ('tattoo', 'performed')])
        self.assertEqual(acts_of(result, 'biopsy'), [('biopsy', 'negated')])
        flow = services.reflow('Tattoo injection [ ] Performed [X] Not\nperformed\nBiopsy [ ] Performed [X] Not '
                               'performed\n[X] Biopsy\n[ ] Snare polypectomy\nTattoo injection [ ] Yes [X] No\n'
                               'Colonoscopy was then performed.\n')
        self.assertEqual(flow.count('\n'), 6)  # only the wrapped option is joined

    def test_a_wrapped_note_is_read_under_its_row(self):
        # formats-1: the note's tail was read as a performed biopsy (a phantom act, a conflict and an unresolved item)
        text, pages = pdf(f'{BANNER}\nColonoscopy report (fictional)\nDate of service: 2026-10-02\n\n'
                          'The colonoscope was advanced to the cecum.\nBiopsy:  [ ] Taken   [X] Not taken - not\n'
                          'sampled before resection\n')
        result = run(text, [('45378', 'The colonoscope was advanced to the cecum.')], pages)[0]
        # the row's own reading denies the biopsy; the tail is read by the row's reader (routing's, over the text as
        # written, holds it across the wrap) and never as a performed act of its own
        self.assertIn(('biopsy', 'negated'), acts_of(result, 'biopsy'))
        self.assertNotIn(('biopsy', 'performed'), acts_of(result, 'biopsy'))
        self.assertEqual(result.services['conflicts'], [])
        self.assertEqual(result.completeness['unresolved_items'], [])

    def test_a_wrapped_note_of_a_row_that_lists_nothing_done_holds(self):
        # formats-1 H2: "Removed today: [ ] Yes [X] No - such lesions are" / "lifted and resected at the EMR unit" read
        # a performed EMR (an unresolved item, and a paid second review at the time)
        text, pages = pdf(f'{BANNER}\nCOLONOSCOPY REPORT (fictional)\nDate of service: 2026-10-02\n\n'
                          'Colonoscopy was performed to the cecum.\nLesion 1\nDescription: 35 mm flat lesion\n'
                          'Removed today:  [ ] Yes   [X] No - such lesions are\nlifted and resected at the EMR unit\n')
        result = run(text, [('45378', 'Colonoscopy was performed to the cecum.')], pages)[0]
        self.assertEqual(acts_of(result, 'emr'), [('emr', 'uncertain')])
        self.assertEqual(result.completeness['unresolved_items'], [])


class SemicolonWrapTests(SimpleTestCase):
    """formats-5 (a): a PDF line that ends at a semicolon inside a sentence ("... candidate for surgery;" / "prior
    studies have been inconclusive.") kept its break, so the next line, starting with a history word, opened a history
    part that dated the documented pH study as history: no unresolved item, coding read complete. A semicolon does not
    end a sentence (_sentences never cuts there), so a lower-case line after it is a soft wrap."""

    INDICATION = 'Indication: Heartburn refractory to PPI; candidate for surgery; prior studies have been inconclusive.'
    PLACEMENT = 'The wireless pH capsule was placed transorally without endoscopy.'

    def reading(self, indication: str):
        text, pages = pdf(f'{BANNER}\nDate of service: 2026-10-05\n\n{indication}\n{self.PLACEMENT}')
        result = run(text, (), pages)[0]
        return (services_of(result), [(u['family'], u['reason']) for u in result.completeness['unresolved_items']],
                result.completeness['state'])

    def test_a_line_wrapped_after_a_semicolon_reads_as_one_sentence(self):
        expected = ([('gi.reflux', 'performed', 'unknown')], [('gi.reflux', 'no_proposal')], 'incomplete')
        self.assertEqual(self.reading(self.INDICATION), expected)  # control: one line
        self.assertEqual(self.reading(self.INDICATION.replace('surgery; prior', 'surgery;\nprior')), expected)

    def test_after_a_semicolon_only_a_lower_case_line_is_joined(self):  # control
        text = 'The colonoscope was advanced to the cecum; the preparation was good;\nPlan: repeat in five years.\n'
        self.assertEqual(services.reflow(text), text)
        text = 'Medications held before the procedure: apixaban for two days;\nprior history of GI bleeding.\n'
        self.assertEqual(services.reflow(text).count('\n'), 1)  # one sentence: the wrap is joined



class ParagraphWithoutBlankLineTests(SimpleTestCase):
    """formats-7: a PDF's text layer (and a Word document whose paragraphs are spaced, not separated by empty ones) has
    no blank line between paragraphs, so a findings paragraph without a final stop ran on into the next one: "No
    polyps; no masses" / "Biopsies were taken." read as one sentence whose "no" denied the biopsy (45380 held with a
    'not performed' statement; with 45378 alone, the biopsy hidden and 45378 READY). A line break the reader keeps
    before a line that opens with a capital and a clause of its own ends the sentence, as a blank line does."""

    M1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-14\n\nThe colonoscope was advanced to the cecum.\n\n'
          'No polyps; no masses\n\nBiopsies were taken.\n')

    def test_the_pdf_reads_the_biopsy_paragraph_as_the_text_does(self):
        text, pages = pdf('\n'.join(line for line in self.M1.split('\n') if line))  # the text layer has no blank line
        self.assertIn('no masses\nBiopsies were taken.', text)
        for source, page_spans in ((self.M1, ()), (text, pages)):
            with self.subTest(pdf=bool(page_spans)):
                result = run(source, [('45380', 'Biopsies were taken.')], page_spans)[0]
                self.assertEqual(acts_of(result, 'biopsy'), [('biopsy', 'performed')])
                self.assertEqual(proposals_of(result)['45380'][0], 'ready')
                missed = run(source, [('45378', 'The colonoscope was advanced to the cecum.')], page_spans)[0]
                self.assertEqual([(u['family'], u['act'], u['reason']) for u in missed.completeness['unresolved_items']],
                                 [('gi.colonoscopy', 'biopsy', 'not_covered')])
                self.assertNotEqual(proposals_of(missed)['45378'][0], 'ready')

    def test_paraphrases_of_the_same_layout(self):
        for paragraph in ('No polyps, masses, ulcers or vascular lesions seen anywhere in the colon or the rectum',
                          'Retroflexion in the rectum was performed; no hemorrhoids',
                          'No polyps or masses were seen in the colon or the rectum, no diverticula'):
            with self.subTest(paragraph=paragraph):
                text = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-14\n\nThe colonoscope was advanced to '
                        f'the cecum.\n{paragraph}\nRandom biopsies were obtained from the right and left colon.\n')
                result = run(text, [('45380', 'Random biopsies were obtained')])[0]
                self.assertEqual(acts_of(result, 'biopsy'), [('biopsy', 'performed')])
                self.assertEqual(proposals_of(result)['45380'][0], 'ready')

    def test_a_wrap_and_a_denied_list_stay_one_sentence(self):  # controls
        cases = (('No biopsy, polypectomy or tattoo was\nperformed today.', 'negated'),  # a lower-case wrap
                 ('No polyp was seen, and no biopsy was taken from the\nSigmoid colon either.', 'negated'),
                 ('Biopsies were sent to Dr.\nSmith Laboratory (fictional) for review.', None))  # no predicate of its own
        for sentence, status in cases:
            with self.subTest(sentence=sentence):
                text = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-14\n\nThe colonoscope was advanced to '
                        f'the cecum.\n{sentence}\n')
                cuts = services._sentences(services.reflow(text))
                start = text.index(sentence.split('\n')[0])
                self.assertTrue(any(s <= start and text.index(sentence.split('\n')[1]) < e for s, e in cuts))
                if status:
                    self.assertIn(('biopsy', status), acts_of(run(text)[0], 'biopsy'))


class AnsweredFieldRowTests(SimpleTestCase):
    """formats-3: reflow joined an answered field row to a following lower-case line ("Biopsies taken from the antrum:
    N" / "pt on apixaban."), so the field's answer was lost and the participle in its label stated the biopsy done (a
    false READY 43239, an unresolved biopsy). A break after a field row is soft only where the join leaves the answer
    the row gives on its own unchanged; a value that genuinely wraps is still joined."""

    EGD = 'The upper endoscope was advanced to the second portion of the duodenum.'

    def read(self, row: str):
        text, pages = pdf(f'{BANNER}\nUPPER ENDOSCOPY REPORT\nDate of service: 2026-10-14\n\n{self.EGD}\n{row}')
        return run(text, [('43239', self.EGD)], pages)[0]

    def test_an_answered_field_row_keeps_its_break_before_a_lower_case_line(self):
        for answer in ('N', 'n', 'no', 'unchecked', 'not checked', 'None'):
            with self.subTest(answer=answer):
                control = self.read(f'Biopsies taken from the antrum: {answer}\nPt on apixaban.')
                result = self.read(f'Biopsies taken from the antrum: {answer}\npt on apixaban.')
                self.assertEqual(acts_of(result, 'biopsy'), acts_of(control, 'biopsy'))
                self.assertNotIn(('biopsy', 'performed'), acts_of(result, 'biopsy'))
                self.assertNotEqual(proposals_of(result)['43239'][0], 'ready')
                self.assertEqual(result.completeness['unresolved_items'], [])

    def test_a_dash_field_keeps_its_break_too(self):
        result = self.read('Biopsy taken from the gastric antrum - N\npt on apixaban.')
        self.assertNotIn(('biopsy', 'performed'), acts_of(result, 'biopsy'))
        self.assertNotEqual(proposals_of(result)['43239'][0], 'ready')

    def test_a_field_value_that_wraps_is_still_joined(self):  # control (ARCHITECTURE 5.9)
        text = ('Findings: a 6 mm sessile polyp in the gastric antrum was removed in one piece\n'
                'with a cold snare and retrieved.\n')
        self.assertEqual(services.reflow(text).count('\n'), 1)
        text = 'Findings: no polyps in the gastric body; a 6 mm sessile polyp was removed in one\npiece.\n'
        self.assertEqual(services.reflow(text).count('\n'), 1)


class TitleLineTests(SimpleTestCase):
    """formats-4: reflow joined a report title to the next line when that line starts in lower case by spelling ("pH
    sensor ...", "s/p ...", "pt ..."), so the title was lost and the documented study read uncertain, historical or
    planned (a hidden missed service, coding read complete). A title written as a heading is never either side of a
    soft wrap; a prose line that happens to end in "report" still wraps."""

    def reading(self, text: str, codes=()):
        text, pages = pdf(text)
        result = run(text, codes, pages)[0]
        return result

    def test_a_title_keeps_its_break_before_a_lower_case_opener(self):
        for opener in ('pH sensor placed at prior manometry.', 'pH catheter in place for 24 hours.',
                       's/p transnasal catheter placement 5 cm above the LES; recording 24 hours off PPI.'):
            with self.subTest(opener=opener):
                head = f'{BANNER}\nDate of service: 2026-10-14\n\nESOPHAGEAL pH IMPEDANCE MONITORING REPORT\n'
                control = self.reading(head + opener[0].upper() + opener[1:] + '\nAcid exposure 7.9%.\n')
                result = self.reading(head + opener + '\nAcid exposure 7.9%.\n')
                self.assertEqual(services_of(control), [('gi.reflux', 'performed', 'unknown')])
                self.assertEqual(services_of(result), services_of(control))
                self.assertEqual(result.completeness['state'], 'incomplete')
                self.assertEqual([(u['family'], u['reason']) for u in result.completeness['unresolved_items']],
                                 [('gi.reflux', 'no_proposal')])

    def test_a_title_case_title_keeps_its_break(self):
        text = (f'{BANNER}\nDate of service: 2026-10-14\n\nEsophageal pH-Impedance Monitoring Report\n'
                'pH catheter in place for 24 hours.\nAcid exposure 7.9%.\n')
        result = self.reading(text, [('91038', 'Acid exposure 7.9%')])
        self.assertEqual(services_of(result), [('gi.reflux', 'performed', 'unknown')])
        self.assertNotIn('service.status', proposals_of(result)['91038'][1])

    def test_a_prose_line_ending_in_report_still_wraps(self):  # control
        text = ('The findings are summarised in the attached colonoscopy report\n'
                'which the patient received.\n')
        self.assertEqual(services.reflow(text).count('\n'), 1)

    def test_a_title_set_on_two_lines_reads_as_one_title(self):
        # formats-5 (d): a scan's narrower lines set the title on two lines; the feeding-tube replacement it names went
        # unread (no service, coding read complete)
        body = ('Date of service: 2026-10-18\n\nProcedure: A new 20 Fr balloon gastrostomy tube was inserted through the '
                'existing tract.\n')
        one = self.reading(f'{BANNER}\nBEDSIDE PROCEDURE NOTE: GASTROSTOMY TUBE REPLACEMENT\n{body}')
        two = self.reading(f'{BANNER}\nBEDSIDE PROCEDURE NOTE: GASTROSTOMY TUBE\nREPLACEMENT\n{body}')
        self.assertEqual(services_of(one), [('gi.feeding_tube', 'performed', 'unknown')])
        self.assertEqual(services_of(two), services_of(one))
        self.assertEqual(two.completeness['state'], one.completeness['state'])
        self.assertEqual(services.reflow('SMALL BOWEL CAPSULE ENDOSCOPY: INTERPRETATION AND\nREPORT\n').count('\n'), 1)

    def test_two_headings_stay_two_headings(self):  # control
        for text in ('COLONOSCOPY REPORT\nFINDINGS\n', 'UPPER ENDOSCOPY WITH BIOPSY\nIMPRESSION\n',
                     'BEDSIDE PROCEDURE NOTE: GASTROSTOMY TUBE REPLACEMENT\nPatient: Synthetic Example (fictional)\n'):
            with self.subTest(text=text):
                self.assertEqual(services.reflow(text), text)
