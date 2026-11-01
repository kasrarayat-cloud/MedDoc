"""GI round 4, package PI: the inventory's own reading of reach, binding and extent (studio/gi/services.py,
validation/checks.required_fact_states, validation/engine._proposal). Declared before coding in
tests/fixtures/gi4/declarations/pi.json. Synthetic documents only; no database, nothing sent.

- S1 (inventory half): the instrument as the subject of its own reach ("The colonoscope reached the cecum") states its
  service performed - only in a procedure report's own document (its head fields, no note written around a procedure,
  no office visit routing reads done), never under another occurrence, never in a clause carrying a date.
- A1: with more than one family performed, an act or lesion no part, name or site gives a family takes the family its
  paragraph last named - same part, never a history, plan or indication part, never a field row, the carried family
  performed, every named site one it reaches, within CARRY_REACH and no blank line between; two families named clear it.
- E1: where routing reads no extent and does not read the family done today, the inventory's own endpoint statement
  supplies the extent - only in a procedure report's own document (its head fields, no note written around a procedure,
  no office visit routing reads done), and never from a history or plan section, under another occurrence, with an
  extent word, or after an earlier-occurrence word.
- W1 (hold-only): an indwelling stent's state is no performed act, dropped only beside another stent performed.

The mutants that must fail these tests, one per guard, are registered in tests/test_gi4_pi_mutants.py (kept apart, so
that a mutant is killed by the behaviour its guard pins, never by its own anchor going missing).
"""
import datetime as dt
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery, regression
from studio.gi import context, detect, services
from studio.types import Fact, Span
from studio.validation import checks

B = battery.B
HEAD = 'Endoscopist: Synthetic Endoscopist, MD (fictional)\nSedation: propofol by a CRNA (fictional)\n'
DAY = dt.date(2026, 10, 19)
TOP = B + 'Upper and Lower Endoscopy\nDate of service: 10/19/2026\n' + HEAD
LOWER = B + 'Lower Endoscopy\nDate of service: 10/19/2026\n' + HEAD
BOTH = 'The gastroscope was advanced to the second part of the duodenum. The colonoscope was advanced to the cecum.'
DOCS = regression.load_fixtures()


def read(text, day=DAY):
    routing = detect.route(text, day)
    return services.build(text, service_date=day, routing=routing, context_facts=context.extract_context(text))


def service(inv, family):
    return next((s for s in inv.services if s.family == family), None)


def acts(inv, kind, family=None):
    return [a for s in inv.services if family is None or s.family == family for a in s.acts if a.kind == kind]


def assess(name, text, codes, answer=None):
    """One battery row through the analyze and assess children (ops.gi4.battery), with a member's date answer."""
    return battery.run_row(battery.modules(), name, text, codes, {'service_date': answer} if answer else None)


class InstrumentReachTests(SimpleTestCase):
    """The instrument as the subject of its own reach, read as performed only with positive evidence."""
    REACH = 'The colonoscope reached the cecum. A polyp was removed with a cold snare.\n'

    def test_a_procedure_report_reads_the_reach_as_performed(self):
        s = service(read(LOWER + self.REACH), 'gi.colonoscopy')
        self.assertEqual((s.status, s.completion, s.extent), ('performed', 'complete', 'cecum'))
        self.assertIn(services._PI_REACH_CUE, s.cues)

    def test_without_a_procedure_head_it_stays_silent(self):
        text = B + 'Lower Endoscopy\nDate of service: 10/19/2026\n' + self.REACH
        self.assertIsNone(service(read(text), 'gi.colonoscopy'))

    def test_never_in_a_note_written_around_a_procedure(self):
        text = B + 'Procedure consent\nDate of service: 10/19/2026\n' + HEAD + self.REACH
        self.assertIsNone(service(read(text), 'gi.colonoscopy'))

    def test_never_under_another_occurrence(self):
        text = LOWER + 'Outside Records Reviewed\n' + self.REACH
        self.assertIsNone(service(read(text), 'gi.colonoscopy'))

    def test_never_in_an_office_visit_note(self):
        # an office note's own "Sedation: none" line passes the head test; routing's office visit holds the reach there
        text = B + 'GI Office Visit\nDate of service: 10/19/2026\nSedation: none (office visit)\n' + self.REACH
        self.assertIn(detect.route(text, DAY).finding('gi.office_em').status, services.POSITIVE)
        self.assertIsNone(service(read(text), 'gi.colonoscopy'))

    def test_never_in_a_clause_carrying_a_date(self):
        text = LOWER + 'The colonoscope reached the cecum after the CT of 09/28/2026 showed a mass.\n'
        self.assertIsNone(service(read(text), 'gi.colonoscopy'))

    def test_the_records_review_and_the_handout_stay_as_installed(self):
        for name in ('J1 records review, unnamed family, long gap', 'J3 teaching handout'):
            text, _ = battery.CASES[name]
            self.assertIsNone(service(read(text), 'gi.colonoscopy'), name)

    def test_h4_04_the_colonoscopy_is_held_not_excluded(self):
        doc = DOCS['h4-04']
        s = service(read(doc['text']), 'gi.colonoscopy')
        self.assertEqual(s.status, 'uncertain')  # the reach read as performed, routing's past negation then doubts it
        self.assertIn(services._PI_REACH_CUE, s.cues)
        quote = 'The colonoscope reached the cecum, where its landmarks, the'
        row = assess('h4-04', doc['text'], [('45378', quote, 'done')], '2026-10-19')
        p = row['proposals']['45378']
        self.assertEqual((p['bucket'], p['status']), ('selected', 'needs_clarification'))
        self.assertIn('performed_status', p['clarifications'])


class ParagraphCarryTests(SimpleTestCase):
    """A1: the service a paragraph is about takes an act or lesion nothing else gives a family."""
    SNARE = 'A polyp was removed with a hot snare.\n'

    def snares(self, text):
        return [(s.family, a.status) for s in read(text).services for a in s.acts if a.kind == 'snare']

    def test_h4_04_the_rectal_polyps_belong_to_the_colonoscopy(self):
        inv = read(DOCS['h4-04']['text'])
        egd, colon = service(inv, 'gi.egd'), service(inv, 'gi.colonoscopy')
        self.assertEqual([l.region for l in egd.lesions], ['stomach'])
        self.assertEqual([l.region for l in colon.lesions], ['rectum'])
        self.assertEqual([(a.kind, a.status) for a in egd.acts], [('snare', 'performed')])  # the antral polyp's snare
        self.assertEqual(services.validate(inv, DOCS['h4-04']['text']), ())

    def test_the_paragraph_carries_its_service(self):
        self.assertEqual(self.snares(TOP + BOTH + '\n' + self.SNARE), [('gi.colonoscopy', 'performed')])

    def test_a_blank_line_ends_the_paragraph(self):
        self.assertEqual(self.snares(TOP + BOTH + '\n\n' + self.SNARE), [])

    def test_beyond_the_carry_reach(self):
        filler = 'The mucosa looked healthy and smooth throughout the whole examined length. ' * 25
        self.assertGreater(len(filler), services.CARRY_REACH)
        self.assertEqual(self.snares(TOP + BOTH + ' ' + filler + self.SNARE), [])

    def test_never_a_field_row(self):
        self.assertEqual(self.snares(TOP + BOTH + '\nPolypectomy by hot snare: performed\n'), [])

    def test_never_to_a_family_not_performed(self):
        text = (B + 'Upper Endoscopy and Flexible Sigmoidoscopy\nDate of service: 10/19/2026\n' + HEAD
                + 'The gastroscope was advanced to the second part of the duodenum. The sigmoidoscope was advanced to '
                  '40 cm. Colonoscopy was deferred. ' + self.SNARE)
        inv = read(text)
        self.assertEqual(self.snares(text), [])
        self.assertNotIn(service(inv, 'gi.colonoscopy').status, services.POSITIVE)

    def test_two_families_named_clear_the_carry(self):
        text = TOP + BOTH + ' Both the EGD and the colonoscopy were tolerated well. ' + self.SNARE
        self.assertEqual(self.snares(text), [])

    def test_never_in_a_history_part(self):
        text = (TOP + 'History\nShe had both examinations in 2023.\nThe colonoscope reached the cecum then.\n'
                + self.SNARE + '\nProcedure\n' + BOTH + '\n')
        self.assertEqual(self.snares(text), [])

    def test_never_into_another_part(self):
        self.assertEqual(self.snares(TOP + BOTH + '\nNursing record\n' + self.SNARE), [])

    def test_a_site_the_carried_family_cannot_reach(self):
        text = (TOP + 'The colonoscope reached the cecum. The gastroscope was advanced to the second part of the duodenum. '
                'A polyp in the sigmoid colon was removed with a cold snare.\nNext colonoscopy in ten years.\n')
        self.assertEqual([f for f, _ in self.snares(text)], [])  # never the upper endoscopy's

    def test_the_bidirectional_report_binds_no_lower_site_to_the_egd(self):
        text = (TOP + 'Stomach and Duodenum\nThe gastroscope was advanced to the second part of the duodenum. In the '
                'gastric antrum sat a 14 mm pedunculated polyp; a hot snare was closed around the stalk and the polyp was '
                'removed and retrieved.\nLarge Bowel\nThe colonoscope reached the cecum, where its landmarks were '
                'photographed. In the rectum, 4 and 6 cm from the anal verge, there were two 3 mm pale polyps, left in '
                'place: no polypectomy was performed in the colon.\n')
        inv = read(text)
        egd = service(inv, 'gi.egd')
        self.assertFalse({x.region for x in egd.acts + egd.lesions} & {'rectum', 'colon', 'anus'})
        self.assertIn('rectum', {l.region for l in service(inv, 'gi.colonoscopy').lesions})


class EndpointExtentTests(SimpleTestCase):
    """E1: the inventory's own endpoint statement supplies the extent routing does not read."""
    TODAY = 'The colonoscope was inserted and a polyp was removed with a cold snare.'

    def extent(self, text):
        return service(read(text), 'gi.colonoscopy').extent

    def test_the_completion_statement_names_the_endpoint(self):
        self.assertEqual(self.extent(LOWER + self.TODAY + ' The cecum was normal.\n'), 'cecum')

    def test_regression_documents(self):
        self.assertEqual(service(read(DOCS['h4-03']['text'], dt.date(2026, 10, 6)), 'gi.egd').extent,
                         'second part of duodenum')
        self.assertEqual(service(read(DOCS['h4-06']['text'], dt.date(2026, 10, 27)), 'gi.colonoscopy').extent,
                         'terminal ileum')

    def test_never_from_a_history_section(self):
        text = (LOWER + 'History: an outside colonoscopy in 2023 was normal.\nThe colonoscope was advanced to the cecum. '
                'A polyp was removed with a cold snare.\n')
        s = service(read(text), 'gi.colonoscopy')
        self.assertEqual((s.completion, s.extent), ('complete', ''))

    def test_never_under_another_occurrence(self):
        self.assertEqual(self.extent(LOWER + self.TODAY + '\nRecords Copied From Mercy\nCecum: normal.\n'), '')

    def test_never_after_an_earlier_occurrence_word_in_the_statement(self):
        text = LOWER + self.TODAY[:-1] + '; at the index examination the cecum was reached.\n'
        self.assertEqual(self.extent(text), '')

    def test_never_from_an_extent_word(self):
        self.assertEqual(self.extent(LOWER + self.TODAY + ' Cecum, the furthest point.\n'), '')

    def test_the_service_extent_counts_only_where_routing_does_not_read_the_family_done(self):
        profile = SimpleNamespace(required_facts=('extent',))
        span = Span(0, 4, 'text')
        s = SimpleNamespace(extent='cecum', completion='complete', completion_evidence=(span,), status='performed')
        silent = SimpleNamespace(facts=(), missing=('extent',), status='historical')
        done = SimpleNamespace(facts=(), missing=('extent',), status='performed')
        state = checks.required_fact_states(profile, silent, {}, service=s)[0]
        self.assertEqual((state.problem, state.fact.value, state.fact.origin), ('', 'cecum', 'document'))
        self.assertEqual(checks.required_fact_states(profile, None, {}, service=s)[0].problem, '')
        self.assertEqual(checks.required_fact_states(profile, done, {}, service=s)[0].problem, 'missing')
        self.assertEqual(checks.required_fact_states(profile, silent, {})[0].problem, 'missing')
        reached = SimpleNamespace(facts=(Fact('extent', 'incomplete: stomach', 'document'),), missing=(), status='uncertain')
        self.assertEqual(checks.required_fact_states(profile, reached, {}, service=s)[0].fact.value, 'incomplete: stomach')

    # an outside banding narrative pasted below its occurrence words, more than OCCURRENCE_HEAD_LINES lines above it
    EVL = 'The gastroscope was withdrawn, fitted with a multiband ligation device and passed again.'
    PASTED = ('\nNotes\nThe patient brought copies from Mercy GI.\n' + battery.FILL
              + 'The gastroscope was passed down the esophagus, through the stomach and pylorus, into the descending '
                'duodenum. The duodenal bulb and descending duodenum were normal.\n' + EVL + ' Six bands were placed.\n')

    def egd_extent(self, text):
        return service(read(text), 'gi.egd').extent

    def test_only_in_a_procedure_report_with_its_own_head(self):
        # positive evidence that the document is today's procedure report (the round's rule for a releasing rule):
        # without a procedure report's own head fields the extent stays a question, as installed
        today = B + 'Variceal Banding Session\nDate of service: 10/19/2026\n'
        self.assertEqual(self.egd_extent(today + HEAD + self.PASTED), 'second part of duodenum')
        self.assertEqual(self.egd_extent(today + self.PASTED), '')
        self.assertEqual(self.egd_extent(B + 'GI Records Review\nDate of service: 10/19/2026\n' + HEAD + self.PASTED), '')

    def test_never_in_an_office_visit_note(self):
        # an office note's own "Sedation: none" line passes the head test; routing's office visit holds E1 there
        note = B + 'Hepatology Office Visit\nDate of service: 10/19/2026\nSedation: none (office visit)\n' + self.PASTED
        self.assertIn(detect.route(note, DAY).finding('gi.office_em').status, services.POSITIVE)
        self.assertEqual(self.egd_extent(note), '')

    def test_a_pasted_outside_banding_narrative_is_never_ready(self):
        for title, extra in (('Hepatology Office Visit', ''), ('GI Records Review', ''),
                             ('Hepatology Office Visit', 'Sedation: none (office visit)\n')):
            text = B + title + '\nDate of service: 10/19/2026\n' + extra + self.PASTED
            p = assess(title, text, [('43244', self.EVL, 'not_done')], '2026-10-19')['proposals']['43244']
            self.assertEqual((p['bucket'], p['status']), ('selected', 'needs_clarification'), title + extra)
            self.assertIn('extent', p['clarifications'], title + extra)

    def test_h4_03_and_h4_06_are_ready_with_the_walk_date(self):
        for doc_id, code, quote, day in (
                ('h4-03', '43244', 'The gastroscope was withdrawn, fitted with a multiband ligation device and passed '
                                   'again.', '2026-10-06'),
                ('h4-06', '45385', 'Transverse colon polyp, 5 mm, removed by cold snare.', '2026-10-27')):
            p = assess(doc_id, DOCS[doc_id]['text'], [(code, quote, 'done')], day)['proposals'][code]
            self.assertEqual((p['bucket'], p['status']), ('selected', 'ready'), doc_id)
            self.assertIn('routing.family', p['checks'], doc_id)  # routing's own reading is still shown

    def test_copied_reports_stay_held(self):
        for name in ('J4 records review, colonoscopy named in plan only', 'J7 records review, completion rows only',
                     'K2 office note with copied EGD named', 'K3 copied colonoscopy, completion statement'):
            text, codes = battery.CASES[name]
            for code, p in assess(name, text, codes)['proposals'].items():
                self.assertEqual((p['bucket'], p['status']), ('selected', 'needs_clarification'), name)
                self.assertIn('performed_status', p['clarifications'], name)


class IndwellingStentTests(SimpleTestCase):
    """W1 (hold-only): an indwelling stent's state is no performed act - dropped only beside another stent placed."""
    ERCP = B + 'ERCP Procedure Note\nDate of service: 10/19/2026\n' + HEAD + '\nProcedure\nThe duodenoscope was advanced to the major papilla. '

    def stents(self, text):
        return [(a.status, a.evidence[0].text) for a in acts(read(text), 'stent')]

    def test_h2_10_the_indwelling_stent_is_no_act_and_43274_stays_ready(self):
        text = DOCS['h2-10']['text']
        found = [t for _, t in self.stents(text) if t.startswith('The existing stent')]
        self.assertEqual(found, [])
        self.assertIn('performed', [s for s, t in self.stents(text) if t.startswith('A new 10 French')])
        quote = 'A new 10 French by 9 cm plastic biliary stent was placed across the stricture, with good drainage of bile and contrast.'
        p = assess('h2-10', text, [('43274', quote, 'MAY')])['proposals']['43274']
        self.assertEqual((p['bucket'], p['status']), ('selected', 'ready'))

    def test_alone_it_stays_as_installed(self):
        text = self.ERCP + 'The existing stent was in position and draining. The bile duct was cannulated.\n'
        self.assertEqual(self.stents(text), [('performed', 'The existing stent was in position and draining.')])

    def test_a_new_stent_placed_beside_it_still_counts(self):
        text = self.ERCP + 'The existing stent was in good position and a second stent was placed beside it.\n'
        self.assertEqual([s for s, _ in self.stents(text)], ['performed'])
