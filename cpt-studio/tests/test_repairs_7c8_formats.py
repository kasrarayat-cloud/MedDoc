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

    PAGE_1 = (f'{BANNER}\nSCREENING COLONOSCOPY\nDate of service: 2026-10-26\n\nProcedure: Colonoscopy.\n'
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
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\n\nThe colonoscope was advanced to the '
                  'splenic flexure; the cecum was not reached.\nPage 1 of 2')
        page_2 = 'Page 2 of 2\nThe procedure was discontinued because of poor preparation.'
        text, pages = pdf(page_1, page_2)
        result, routing = run(text, [('45378', 'COLONOSCOPY REPORT')], pages)
        self.assertEqual([(f.family, f.status) for f in routing.findings], [('gi.colonoscopy', 'incomplete')])
        self.assertEqual(services_of(result), [('gi.colonoscopy', 'incomplete', 'incomplete')])

    def test_a_heading_after_a_finished_sentence_is_no_furniture(self):  # control (must not change)
        # page 1 ends with a finished sentence and page 2 opens with a section heading over a lower-case line: the
        # heading is the document's, never skipped as furniture
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\n\nThe colonoscope was advanced to the '
                  'cecum and the examination was complete.')
        page_2 = 'FINDINGS\nrandom biopsies were taken from the right and left colon.'
        text, pages = pdf(page_1, page_2)
        self.assertIn('FINDINGS', services.reflow(text, pages))

    def test_an_instrument_and_its_predicate_across_the_furniture(self):
        # sk:2, formats-5 (b): the performed EGD went unread and coding read complete
        page_1 = (f'{BANNER}\nOPERATIVE NOTE\nDate of service: 2026-10-14\n\nWith the patient in the left lateral '
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
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-08\n\nPlace of service: Ambulatory surgery '
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
        page_1 = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-08\n\nThe colonoscope was advanced to the '
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

    HEAD = f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-26\n\nThe colonoscope was advanced to the cecum. '

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


class WrappedRowContinuationTests(SimpleTestCase):
    """sk:4 (formats-0) and sk:9 (formats-1): a check-box row whose marked option is cut after its negation ("[X] Not" /
    "Performed", "Done", "PERFORMED"), or whose note is cut inside a name ("- referred to Halcyon" / "Valley EMR unit
    (fictional), where ...", "- per Dr." / "Okafor (fictional), biopsies are taken ..."), was joined only to a
    lower-case continuation: the title-case option lost the nursing denial (the physician-vs-nursing tattoo conflict,
    45381 READY: the Elena tattoo-conflict class), and the note's tail read as free prose (a performed EMR or biopsy, a
    conflict and an unresolved item). A row whose option or note cannot end where its line does goes on in the next
    line whatever its case, when that line has no mark of its own and opens no clause, row, field or item of its own."""

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
        self.assertEqual(proposals_of(result)['45381'][0], 'needs_clarification')
        self.assertIn('conflict:tattoo', [q.fact for p in result.proposals for q in p.clarifications])

    def test_the_unwrapped_title_case_row(self):  # control
        self.assert_conflict(self.read('Tattoo injection [ ] Performed [X] Not Performed\n'))

    def test_a_title_case_option_wrapped_after_its_negation(self):
        for rows in ('Tattoo injection            [ ] Performed   [X] Not\nPerformed\n',
                     'Tattoo injection            [ ] Done   [X] Not\nDone\n',
                     'TATTOO INJECTION            [ ] PERFORMED   [X] NOT\nPERFORMED\n'):
            with self.subTest(rows=rows):
                self.assert_conflict(self.read(rows))

    def test_an_agreeing_title_case_row_stays_ready(self):  # control
        result = self.read('Tattoo injection            [X] Performed   [ ] Not\nPerformed\n')
        self.assertEqual(result.services['conflicts'], [])
        self.assertEqual(proposals_of(result)['45381'], ('ready', []))

    def test_the_corpus_row_in_title_case_keeps_its_conflict_at_every_width(self):
        # the skeptic's corpus form: svc-21 with "[X] Not Performed", as a PDF at the widths that cut it after "Not"
        from pathlib import Path

        from tests.test_services_formats_corpus import pages as corpus_pages
        from tests.test_services_formats_corpus import reading as corpus_reading
        path = (Path(__file__).resolve().parent / 'corpus' / 'services' / 'documents'
                / 'svc-21-colo-emr-tattoo-clips-nursing-conflict.txt')
        text = path.read_text(encoding='utf-8').replace('[X] Not performed', '[X] Not Performed')
        expected = sorted(x for x in corpus_reading(text) if x[0] == 'conflict')
        self.assertEqual(expected, [('conflict', 'gi.colonoscopy', 'tattoo')])
        for width in range(51, 61):
            with self.subTest(width=width):
                result = extract_document(docgen.make_pdf(corpus_pages(text, width, 44)), 'c.pdf', 'application/pdf')
                got = sorted(x for x in corpus_reading(result.text, result.pages) if x[0] == 'conflict')
                self.assertEqual(got, expected)

    NOTE_HEAD = (f'{BANNER}\nCOLONOSCOPY REPORT (fictional)\nDate of service: 2026-10-02\n\n'
                 'Colonoscopy was performed to the cecum.\nLesion 1\nDescription: 35 mm flat lesion\n')
    NOTE_CITE = [('45378', 'Colonoscopy was performed to the cecum.')]

    def note(self, row: str):
        text, pages = pdf(self.NOTE_HEAD + row + '\n')
        return run(text, self.NOTE_CITE, pages)[0]

    def test_a_note_wrapped_inside_a_name_is_read_under_its_row(self):
        for one, two in (('Removed today:  [ ] Yes   [X] No - referred to Halcyon Valley EMR unit (fictional), where '
                          'the lesion is lifted and resected',
                          'Removed today:  [ ] Yes   [X] No - referred to Halcyon\nValley EMR unit (fictional), where '
                          'the lesion is lifted and resected'),
                         ('Biopsy:  [ ] Taken   [X] Not taken - per Dr. Okafor (fictional), biopsies are taken only '
                          'after the lesion is resected',
                          'Biopsy:  [ ] Taken   [X] Not taken - per Dr.\nOkafor (fictional), biopsies are taken only '
                          'after the lesion is resected')):
            with self.subTest(two=two):
                control, result = self.note(one), self.note(two)
                for reading in (control, result):
                    self.assertNotIn(('emr', 'performed'), acts_of(reading))
                    self.assertNotIn(('biopsy', 'performed'), acts_of(reading))
                    self.assertEqual(reading.services['conflicts'], [])
                    self.assertEqual(unresolved_of(reading), [])
                # the note's own act is held (its printed line read alone) or read as the one line reads it
                self.assertTrue(set(acts_of(result)) <= set(acts_of(control)) | {(a, 'uncertain') for a, _ in acts_of(result)})

    def test_a_note_that_ends_keeps_its_break(self):  # controls: a new sentence, a heading, a field after a row
        for text in ('Biopsy:  [ ] Taken   [X] Not taken - deferred\nColonoscopy was then completed to the cecum.\n',
                     'Removed today:  [ ] Yes   [X] No - see below\nFINDINGS\n',
                     'Removed today:  [ ] Yes   [X] No - referred to Halcyon\nPlan: repeat colonoscopy in 3 years.\n',
                     'Tattoo injection [ ] Yes [X] No\nColonoscopy was then performed.\n',
                     'Tattoo injection [ ] Performed [X] Not\n[X] Biopsy\n',
                     '1. [x] Procedures performed:\nCold snare polypectomy of the 6 mm sigmoid polyp.\n',
                     '- [ ] Procedures not performed:\nCold snare polypectomy of the 6 mm sigmoid polyp.\n'):
            with self.subTest(text=text):
                self.assertEqual(services.reflow(text), text)


class ParagraphOpeningWithANumeralOrAVerbTests(SimpleTestCase):
    """sk:5 (formats-7): a PDF's text layer and a Word document's paragraphs carry no blank line, so a findings
    paragraph without a final stop ran on into the next one when that one opened with a numeral ("2 biopsies were
    taken") or with its verb ("Biopsied the sigmoid colon"): "no masses" denied the biopsy, so with 45378 alone the
    biopsy was hidden and 45378 READY (with 45380, held). Such a line opens a sentence of its own, as a capitalised
    subject and its predicate do."""

    def document(self, paragraph: str, blank: bool):
        sep = '\n\n' if blank else '\n'
        return (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-14\n\nThe colonoscope was advanced to the '
                f'cecum.{sep}No polyps; no masses{sep}{paragraph}\n')

    def readings(self, paragraph: str, codes):
        text = self.document(paragraph, True)
        out = [run(text, codes)[0]]
        ptext, ppages = pdf(self.document(paragraph, False))
        out.append(run(ptext, codes, ppages)[0])
        paragraphs = [p for p in text.split('\n') if p]
        docx = extract_document(docgen.make_docx(paragraphs), 'synthetic.docx',
                                'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(docx.status, 'ok', docx.messages)
        out.append(run(docx.text, codes, docx.pages)[0])
        return out

    def test_the_pdf_and_word_readings_equal_the_text(self):
        for paragraph, quote in (('2 biopsies were taken from the sigmoid colon.', '2 biopsies were taken'),
                                 ('Biopsied the sigmoid colon at 20 cm.', 'Biopsied the sigmoid colon')):
            with self.subTest(paragraph):
                for result in self.readings(paragraph, [('45378', 'The colonoscope was advanced to the cecum.')]):
                    self.assertEqual(acts_of(result, 'biopsy'), [('biopsy', 'performed')])
                    self.assertEqual(unresolved_of(result), [('gi.colonoscopy', 'biopsy', 'not_covered')])
                    self.assertNotEqual(proposals_of(result)['45378'][0], 'ready')
                for result in self.readings(paragraph, [('45380', quote)]):
                    self.assertEqual(proposals_of(result)['45380'], ('ready', []))

    def test_a_measure_or_a_wrap_on_the_next_line_stays_in_its_sentence(self):  # controls
        for sentence in ('The flat polyp found in the proximal sigmoid colon near the fold measured\n5 mm and was removed with a cold snare.',
                         'No polyp was seen, and no biopsy was taken at\n20 cm in the sigmoid colon.',
                         'A single sessile polyp with a central depression was seen in the descending colon\nMeasuring 6 mm in size.'):
            with self.subTest(sentence=sentence):
                first, second = sentence.split('\n')
                text = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-14\n\nThe colonoscope was advanced to '
                        f'the cecum.\n{sentence}\n')
                cuts = services._sentences(services.reflow(text))
                self.assertTrue(any(s <= text.index(first) and text.index(second) < e for s, e in cuts))


class TitleNamingAServiceTests(SimpleTestCase):
    """sk:6 (formats-4) and sk:7 (formats-5 d): a title written as a heading that names its service without a report
    word ("24-HOUR ESOPHAGEAL pH MONITORING", "HIGH RESOLUTION ESOPHAGEAL MANOMETRY") was joined to a next line that is
    lower case by spelling ("pH sensor ...", "s/p ...", "pt ..."), and a title set on two short heading lines
    ("GASTROSTOMY TUBE" / "REPLACEMENT"), or three ("BEDSIDE PROCEDURE NOTE:" / ...), was never one title: the study
    or the tube replacement went unread (or read historical), so coding read complete. A heading that names a service
    keeps its break whatever the next line's case, and one title set on several heading lines reads as one."""

    def reading(self, text: str):
        text, pages = pdf(text)
        result = run(text, (), pages)[0]
        return services_of(result), [(u['family'], u['reason']) for u in result.completeness['unresolved_items']], \
            result.completeness['state']

    def test_a_service_heading_keeps_its_break_before_a_lower_case_opener(self):
        head = f'{BANNER}\nDate of service: 2026-10-14\n\n'
        for title, family in (('24-HOUR ESOPHAGEAL pH MONITORING', 'gi.reflux'),
                              ('WIRELESS pH CAPSULE STUDY', 'gi.reflux'),
                              ('AMBULATORY pH MONITORING (BRAVO)', 'gi.reflux'),
                              ('HIGH RESOLUTION ESOPHAGEAL MANOMETRY', 'gi.motility')):
            for opener in ('pH sensor placed at prior manometry.', 'pH catheter in place for 24 hours.',
                           'pt tolerated the study well.',
                           's/p transnasal catheter placement 5 cm above the LES; recording 24 hours off PPI.'):
                with self.subTest(title=title, opener=opener):
                    control = self.reading(head + title + '\n' + opener[0].upper() + opener[1:] + '\nAcid exposure '
                                                                                                 '7.9%.\n')
                    result = self.reading(head + title + '\n' + opener + '\nAcid exposure 7.9%.\n')
                    self.assertEqual(result, control)
                    self.assertEqual(result[2], 'incomplete')
                    self.assertIn((family, 'no_proposal'), result[1])

    def test_prose_naming_a_service_still_wraps(self):  # control
        text = 'The patient was referred for esophageal pH monitoring\nwhich showed acid reflux.\n'
        self.assertEqual(services.reflow(text).count('\n'), 1)

    def test_a_title_set_on_several_short_heading_lines(self):
        body = ('Date of service: 2026-10-18\n\nProcedure: A new 20 Fr balloon gastrostomy tube was inserted through the '
                'existing tract.\n')
        one = self.reading(f'{BANNER}\nGASTROSTOMY TUBE REPLACEMENT\n{body}')
        self.assertEqual(one, ([('gi.feeding_tube', 'performed', 'unknown')], [('gi.feeding_tube', 'no_proposal')],
                               'incomplete'))
        for title in ('GASTROSTOMY TUBE\nREPLACEMENT', 'BEDSIDE PROCEDURE NOTE:\nGASTROSTOMY TUBE\nREPLACEMENT'):
            with self.subTest(title=title):
                self.assertEqual(self.reading(f'{BANNER}\n{title}\n{body}'), one)

    def test_two_short_headings_stay_two(self):  # controls
        for text in ('COLONOSCOPY REPORT\nFINDINGS\n', 'IMPRESSION\nPLAN\n', 'EGD\nFINDINGS\n',
                     'UPPER ENDOSCOPY\nCOLONOSCOPY\n'):
            with self.subTest(text=text):
                self.assertEqual(services.reflow(text), text)


class HistoryWordsOpeningASentenceTests(SimpleTestCase):
    """sk:8 (formats-5 a): the PDF writer's wrap put "Prior studies have been inconclusive." at the start of a line,
    where it opened a history part, so the pH capsule placed today read historical (no unresolved item, coding
    complete); the text, with the sentence mid-line, reads it performed. A line opens a history part only as a
    heading: a sentence whose history words are its own subject is no heading of what follows."""

    PLACEMENT = 'The wireless pH capsule was placed transorally without endoscopy.'

    def reading(self, text, pages=()):
        result = run(text, (), pages)[0]
        return services_of(result), [(u['family'], u['reason']) for u in result.completeness['unresolved_items']], \
            result.completeness['state']

    def test_the_pdf_reads_as_the_text(self):
        source = (f'{BANNER}\nDate of service: 2026-10-05\n\nIndication: Heartburn refractory to proton pump inhibitor '
                  f'therapy; candidate for surgery. Prior studies have been inconclusive.\n{self.PLACEMENT}\n')
        expected = ([('gi.reflux', 'performed', 'unknown')], [('gi.reflux', 'no_proposal')], 'incomplete')
        self.assertEqual(self.reading(source), expected)
        text, pages = pdf(source)
        self.assertIn('surgery.\nPrior studies have been inconclusive.', text)  # the PDF writer's wrap
        self.assertEqual(self.reading(text, pages), expected)

    def test_a_history_heading_still_opens_a_history_part(self):  # control
        text = (f'{BANNER}\nDate of service: 2026-10-05\n\nPrior studies:\nWireless pH capsule placed in 2024; acid '
                f'exposure 9%.\nToday: {self.PLACEMENT}\n')
        parts = services.parts(text)
        heading = text.index('Prior studies:')
        self.assertTrue(any(p.kind == 'history' and p.start <= heading < p.end for p in parts))
        # a history sentence that opens no labelled section's paragraph still heads the lines after it, as before
        text = (f'{BANNER}\nDate of service: 2026-10-05\n\nPast medical history is notable for the following.\n'
                'Polypectomy.\nHemorrhoid banding.\n')
        item = text.index('Polypectomy.')
        self.assertTrue(any(p.kind == 'history' and p.start <= item < p.end for p in services.parts(text)))


class LabelAnsweredOnTheNextLineTests(SimpleTestCase):
    """sk:10 (formats-3): the PDF writer wrapped a field row right after its colon ("Biopsies taken from the gastric
    antrum and the gastric body for Helicobacter pylori (CLO):" / "no, pt on apixaban."), the label line kept its
    break, and the label's participle read the biopsy done: 43239 READY, where the text on one line holds it. A field
    label that names an act, with no answer on its line, is answered by the next line when that line opens with a short
    answer: the two are one line."""

    EGD = 'The upper endoscope was advanced to the second portion of the duodenum.'
    LABEL = 'Biopsies taken from the gastric antrum and the gastric body for Helicobacter pylori (CLO):'

    def read(self, text, pages=()):
        result = run(text, [('43239', self.EGD)], pages)[0]
        return acts_of(result, 'biopsy'), proposals_of(result)['43239'][0]

    def test_the_pdf_reads_as_the_one_line_text(self):
        for answer in ('no, pt on apixaban.', 'No, pt on apixaban.', 'no', 'No', 'N', 'none'):
            with self.subTest(answer=answer):
                source = f'{BANNER}\nUPPER ENDOSCOPY REPORT\nDate of service: 2026-10-14\n\n{self.EGD}\n{self.LABEL} {answer}\n'
                control = self.read(source)
                self.assertNotIn(('biopsy', 'performed'), control[0])
                self.assertNotEqual(control[1], 'ready')
                text, pages = pdf(source)
                self.assertIn('(CLO):\n', text)  # the PDF writer's wrap after the colon
                self.assertEqual(self.read(text, pages), control)

    def test_a_label_over_its_paragraph_keeps_its_break(self):  # controls
        for text in ('Findings:\nNo polyps were seen in the colon.\n',
                     'Biopsies taken:\nNone of the three polyps could be retrieved for histology.\n',
                     'Biopsies taken from the gastric antrum for CLO:\nThe rapid urease test was negative.\n'):
            with self.subTest(text=text):
                self.assertEqual(services.reflow(text), text)


class ActFrameReadsThePageJoinTests(SimpleTestCase):
    """sk:11: the routing-era exclusion of a code whose family no documented service names is held when the
    documented-service reader reads an act in the code's passage as done today (services.states_an_act_done); that
    reader's view (_act_frame) was reflowed without the revision's page spans, so across a page join it read nothing,
    and 46221 was EXCLUDED for two rubber bands the document places today ("... two rubber bands were" / "placed on
    the internal hemorrhoids today."). It reads the same page-joined view as build()."""

    HEAD = (f'{BANNER}\nProcedure date: 10/14/2026\n\nPROCEDURE NOTE: Anoscopy with hemorrhoid banding\nIndication: '
            'Bleeding internal hemorrhoids.\nFindings: Grade 2 internal hemorrhoids were seen.\n')

    def test_a_banding_across_a_page_join_is_never_excluded(self):
        for first, second in (('After the previous banding failed, two rubber bands were',
                               'placed on the internal hemorrhoids today.'),
                              ('Although banding had been planned for next month, two rubber bands were',
                               'placed on the internal hemorrhoids today.'),
                              ('After the previous banding failed two years ago, two rubber bands were',
                               'placed today.')):
            with self.subTest(first=first):
                one_text, one_pages = pdf(self.HEAD + first + '\n' + second + '\nImpression: See findings.')
                one = run(one_text, [('46221', first + '\n' + second)], one_pages)[0]
                text, pages = pdf(self.HEAD + first, second + '\nImpression: See findings.')
                quote = first + '\n\n\n' + second
                self.assertIn(quote, text)
                two = run(text, [('46221', quote)], pages)[0]
                self.assertNotEqual(proposals_of(one)['46221'][0], 'excluded')  # control: one page holds it
                self.assertNotEqual(proposals_of(two)['46221'][0], 'excluded')
                at = text.index(quote)
                self.assertIsNotNone(services.states_an_act_done(text, at, at + len(quote), date(2026, 10, 14),
                                                                 pages))


class FieldAnswerCostTests(SimpleTestCase):
    """sk:13 (outside FORMATS, COST class 2, pre-existing at 8985dde42): routing's field-answer reader
    (sections._FIELD_ANSWER, read at every line end by _answered and _answered_line) let a run of spaces be shared every
    way between its opening run, a label that may hold spaces and the space before the separator: a line whose last 200
    characters hold a long run of spaces took about a second ("Withdrawal time" + 170 spaces + "9 minutes."), and 120
    such lines took the assess stage past its limit. The runs are read once (possessive), so the cost is linear."""

    def test_the_assess_stage_reads_many_spaced_rows_in_time(self):
        from tests.test_repairs_r7_cost import assess_child
        text = (f'{BANNER}\nCOLONOSCOPY REPORT\nDate of service: 2026-10-21\n\n'  # the date assess_child assesses for
                + ''.join(f'Colonoscopy {i}: the procedure was not' + ' ' * 170 + 'discontinued; it was completed.\n'
                          for i in range(120)))
        at = text.index('COLONOSCOPY REPORT')
        proposals = assess_child(text, '45378', [(at, at + len('COLONOSCOPY REPORT'))])
        self.assertIn('45378', proposals)

    def test_the_answers_read_as_before(self):  # the readings the pattern gives are unchanged
        from studio.gi import sections
        for tail, answered in (('Hiatal hernia: no', True), ('Hiatal hernia - no', True), ('Hiatal hernia? never', True),
                               ('Sedation: patient declined', True), ('Hiatal hernia\tno', True),
                               ('Hiatal hernia: no, Schatzki ring: no', True), ('Mucosa: normal,   hiatal hernia: no', True),
                               ('Hiatal hernia: no   Schatzki ring: no', True), ('Withdrawal time' + ' ' * 170 + '9 minutes.', False),
                               ('Colonoscopy was performed - no EGD was done', False), ('Biopsies: taken', False),
                               ('   Hiatal hernia:   none', True), ('Ring = no', True), ('a  b: no', True),
                               ('Biopsies taken.    - no', True), ('Biopsies taken. - no', False)):
            with self.subTest(tail=tail):
                self.assertEqual(sections._answered(tail), answered)


class AnotherEventsDateAfterTheActsOwnTodayTests(SimpleTestCase):
    """sk:12 (outside FORMATS, EXCL class 4, pre-existing at 8985dde42): "Two polyps were removed with a cold snare
    today because the polypectomy in 2025 had been incomplete." excluded 45385 as historical: the date of the clause
    "because the polypectomy in 2025 had been incomplete" was read as the act's own, since that clause's predicate comes
    after the date. A date inside a clause another event opens (because, after, since ...) is that event's whenever
    the clause has a predicate of its own, before or after the date; the act is never excluded on it."""

    HEAD = (f'{BANNER}\nProcedure date: 10/14/2026\n\nPROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced '
            'to the cecum.\nFindings: ')
    ANOSCOPY = (f'{BANNER}\nProcedure date: 10/14/2026\n\nPROCEDURE NOTE: Anoscopy with hemorrhoid banding\nIndication: '
                'Bleeding internal hemorrhoids.\nFindings: ')

    def test_the_act_stated_done_today_is_never_excluded(self):
        for head, line, code in (
                (self.HEAD, 'Two polyps were removed with a cold snare today because the polypectomy in 2025 had been '
                            'incomplete.', '45385'),
                (self.HEAD, 'Biopsies were taken from the sigmoid colon today because the biopsies in 2025 had been '
                            'nondiagnostic.', '45380'),
                (self.ANOSCOPY, 'Two rubber bands were placed on the internal hemorrhoids today because the banding in '
                                '2025 had failed.', '46221')):
            with self.subTest(line=line):
                text = head + line + '\nImpression: See findings.\n'
                result = run(text, [(code, line)])[0]
                self.assertNotEqual(proposals_of(result)[code][0], 'excluded')

    def test_a_dated_phrase_still_dates_the_act(self):  # control: "since 2019" opens no clause of its own
        text = self.HEAD + 'Polyps have been removed with a cold snare at annual colonoscopies since 2019.\n'
        result = run(text)[0]
        self.assertIn(('snare', 'historical'), acts_of(result, 'snare'))
