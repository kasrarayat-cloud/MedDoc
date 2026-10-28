"""GI round 2, repair "attribution" (session 7c8d38da; investigation key "demo", RC4/RC5).

RC4 (ho-08): a manometry act was given to the one endoscopy a manometry report names - "An EGD on 2026-09-08 showed
..." in its indication - so the report read "Upper GI endoscopy - performed (manometry)", asked how far that EGD's
instrument was advanced, listed it as a performed service without a proposal, and held 91010 on a results-table row.
A study act (manometry, pH or impedance monitoring, rectal sensation testing) belongs to its own study service or to
none; the study's name reads in either word order ("Esophageal High-Resolution Manometry"); and a passage of the
study's own report (its results, its interpretation) shows the study and never holds its code by its section alone.

RC5 (ho-09): 46221 was ready on "Sedation: None." and the sigmoidoscope's advance, unchecked, beside "band ligation of two
columns through the flexible sigmoidoscope". Where the inventory documents no service of a code's family but documents
the act the code accounts for in another family's service, the code's passages are checked against that act and the
service holding it is named - a support finding, never a hold, an added code or a promoted alternative.

Every document is synthetic and written for this module; the expected outcome is written here, outside the coding
input. Author expectations stay provisional (ho-08: 91010 with 26; ho-09: 45350, "not 46221"): nothing here asserts a
code is right, only what the document documents and what the engine says about it.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.gi import context as gi_context
from studio.gi import detect
from studio.gi import services as gi_services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
# The acts only a physiology study performs (written out, so the test never reads its expectation from the code).
STUDY_KINDS = ('manometry', 'ph_monitoring', 'rectal_sensation')


def span(text, phrase):
    start = text.index(phrase)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def facts_and_day(text):
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    return facts, day


def inventory(text):
    facts, day = facts_and_day(text)
    return gi_services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)


def run(text, codes):
    """``codes``: (code, [cited phrases]) the provider selected, each phrase an exact passage of ``text``."""
    facts, day = facts_and_day(text)
    selected = tuple(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING', tuple(span(text, p) for p in ps))
                     for code, ps in codes)
    return assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', selected),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def proposal(result, code):
    found = [p for p in result.proposals if p.code == code and p.bucket != 'alternative']
    assert found, f'{code} not in {[p.code for p in result.proposals]}'
    return found[0]


def check(item, check_id):
    return next((c for c in item.checks if c.id == check_id), None)


def performed(inv, family):
    return [s for s in inv.services if s.family == family and s.status in ('performed', 'incomplete')]


# A study's own report: the modifier after the organ in its title, its only endoscopy an earlier one in the indication
# and two planned ones in the recommendations.
HRM = HEADER + """Esophageal High-Resolution Manometry Report
Place of service: Hospital outpatient department (POS 22)
Date of service: 2026-10-13
Interpreting physician: Ada Quill-Fictional, MD (fictional)
Billing: Professional component only (interpretation and report).

Indication
Dysphagia to solids and liquids for six months. An EGD on 2026-09-08 showed a dilated esophagus with retained fluid.

Technique
A solid-state high-resolution manometry catheter was placed through the nose by the motility nurse after topical
anesthesia, without endoscopic guidance. Ten 5 mL water swallows were given supine and five upright.

Results
Measure | Supine | Upright
Median integrated relaxation pressure (mmHg) | 27.9 | 23.0
Failed peristalsis | 10 of 10 swallows | 5 of 5 swallows

Interpretation
Type II achalasia by Chicago Classification version 4.0: elevated integrated relaxation pressure and 100 percent failed
peristalsis.

Recommendations
Treatment options are peroral endoscopic myotomy or pneumatic dilation.

Electronically signed: Ada Quill-Fictional, MD (fictional), 2026-10-13
"""
ROW = 'Median integrated relaxation pressure (mmHg) | 27.9 | 23.0'
READING = 'Type II achalasia by Chicago Classification version 4.0'


class StudyActsBelongToTheirStudyTests(SimpleTestCase):
    """RC4: a study act is never an act of an endoscopy, whatever part of the document names it."""

    def test_the_manometry_act_is_the_manometry_s_and_the_earlier_egd_stays_earlier(self):
        inv = inventory(HRM)
        self.assertEqual(performed(inv, 'gi.egd'), [], [(s.family, s.status, [a.kind for a in s.acts])
                                                          for s in inv.services])
        self.assertFalse(any(a.kind == 'manometry' for s in inv.services if s.family == 'gi.egd' for a in s.acts))
        motility = performed(inv, 'gi.motility')
        self.assertEqual(len(motility), 1)
        self.assertTrue(any(a.kind == 'manometry' and a.status == 'performed' for a in motility[0].acts))

    def test_no_extent_is_asked_of_an_endoscopy_not_performed_today(self):
        result = run(HRM, [('91010', [ROW])])
        self.assertNotIn(('service', 'gi.egd', 'extent'), [(c.scope, c.family, c.fact) for c in result.clarifications])
        self.assertEqual([u for u in result.completeness['unresolved_items'] if u['family'] == 'gi.egd'], [])

    def test_a_study_named_in_no_form_the_reader_knows_is_still_never_an_endoscopy_act(self):
        """Without a title the reader recognises, the study act belongs to no service - never to the earlier EGD (or
        sigmoidoscopy) the document names, which no study act makes performed today, and of which no extent is asked."""
        cases = {
            'manometry': ('Motility Laboratory Note', 'An EGD on 2026-09-01 showed a dilated esophagus.',
                          'A high-resolution manometry catheter was placed through the nose by the nurse.', 'gi.egd'),
            'ph': ('Ambulatory Study Note', 'An EGD on 2026-08-01 showed esophagitis.',
                   'A pH catheter was placed through the nose and the recording was started.', 'gi.egd'),
            'rectal sensation': ('Pelvic Floor Laboratory Note', 'A flexible sigmoidoscopy on 2026-07-01 was normal.',
                                 'Rectal sensation was recorded with a balloon catheter.', 'gi.flex_sig'),
        }
        for name, (title, earlier, act, family) in cases.items():
            with self.subTest(name):
                text = HEADER + f'{title}\nDate of service: 2026-10-14\nIndication\n{earlier}\nProcedure\n{act}\n'
                inv = inventory(text)
                self.assertEqual(performed(inv, family), [], [(s.family, s.status, [a.kind for a in s.acts])
                                                               for s in inv.services])
                result = run(text, [])
                self.assertNotIn('extent', [c.fact for c in result.clarifications if c.family == family])
                self.assertEqual([u for u in result.completeness['unresolved_items'] if u['family'] == family], [])

    def test_an_impedance_reading_during_an_endoscopy_is_no_act_of_it(self):
        text = HEADER + ('Date of service: 2026-10-14\nUpper endoscopy report\nThe gastroscope was advanced to the second '
                         'portion of the duodenum. Impedance planimetry was performed at the gastroesophageal junction.\n')
        egd = performed(inventory(text), 'gi.egd')
        self.assertEqual(len(egd), 1)  # still performed, by its own statement
        self.assertEqual([a.kind for a in egd[0].acts if a.kind in STUDY_KINDS], [])

    def test_control_a_same_session_endoscopy_keeps_its_own_reading(self):
        text = HEADER + ('Date of service: 2026-10-14\nProcedure\nAn EGD was performed. The gastroscope was advanced to '
                         'the second portion of the duodenum. The esophagus was normal. After the EGD, esophageal '
                         'manometry was performed and a manometry catheter was placed through the nose.\n')
        inv = inventory(text)
        egd = performed(inv, 'gi.egd')
        self.assertEqual(len(egd), 1)
        self.assertEqual(egd[0].completion, 'complete')
        self.assertEqual([a.kind for a in egd[0].acts if a.kind in STUDY_KINDS], [])
        motility = performed(inv, 'gi.motility')
        self.assertEqual(len(motility), 1)
        self.assertIn('manometry', [a.kind for a in motility[0].acts])

    def test_control_each_study_act_still_reaches_its_own_named_study(self):
        text = HEADER + ('Anorectal Manometry Report\nDate of service: 2026-10-14\nTechnique\nAnorectal manometry was '
                         'performed with a solid-state catheter. Rectal sensation testing was performed and the balloon '
                         'expulsion test was completed.\n')
        anorectal = performed(inventory(text), 'gi.anorectal')
        self.assertEqual(len(anorectal), 1)
        self.assertTrue({'manometry', 'rectal_sensation'} <= {a.kind for a in anorectal[0].acts}, anorectal[0].acts)


class TheStudysOwnReportTests(SimpleTestCase):
    """RC4: the study's name reads in either word order, and a passage of its own report never decides its status by
    its section alone."""

    def test_the_study_name_reads_with_its_modifier_on_either_side_of_the_organ(self):
        for name in ('Esophageal High-Resolution Manometry', 'esophageal high resolution manometry',
                     'High-resolution esophageal manometry', 'Esophageal manometry'):
            with self.subTest(name):
                self.assertEqual(gi_services._family_named(name)[0], 'gi.motility')

    def test_a_results_row_of_the_study_s_own_report_never_holds_its_code(self):
        result = run(HRM, [('91010', [ROW, READING])])
        item = proposal(result, '91010')
        self.assertEqual(item.status, 'ready', [(c.id, c.status, c.detail) for c in item.checks])
        self.assertEqual([c.fact for c in item.clarifications], [])
        self.assertEqual(check(item, 'service.status').status, 'pass', check(item, 'service.status').detail)
        support = check(item, 'evidence.support')
        self.assertEqual(support.status, 'pass', support.detail)  # its results and its interpretation are the study's
        self.assertEqual(item.support['supporting'], [0, 1])

    def test_control_a_hedge_in_the_study_s_own_report_still_holds(self):
        text = HRM.replace('Failed peristalsis |', 'The recording was possibly incomplete?\nFailed peristalsis |')
        item = proposal(run(text, [('91010', ['The recording was possibly incomplete?'])]), '91010')
        self.assertEqual(item.status, 'needs_clarification')

    def test_control_passages_of_its_indication_and_plan_never_show_the_study(self):
        item = proposal(run(HRM, [('91010', ['An EGD on 2026-09-08 showed a dilated esophagus with retained fluid.',
                                             'Treatment options are peroral endoscopic myotomy or pneumatic dilation.'])]),
                        '91010')
        self.assertEqual(check(item, 'evidence.support').status, 'warn')
        self.assertEqual(item.support['unrelated'], [0, 1])

    def test_control_a_header_or_signature_line_never_shows_the_study(self):
        item = proposal(run(HRM, [('91010', ['Billing: Professional component only (interpretation and report).',
                                             'Electronically signed: Ada Quill-Fictional, MD (fictional), 2026-10-13'])]),
                        '91010')
        self.assertEqual(check(item, 'evidence.support').status, 'warn')
        self.assertEqual(item.support['unrelated'], [0, 1])

    def test_control_without_the_study_s_own_report_a_section_only_row_still_holds(self):
        text = HRM.replace('Esophageal High-Resolution Manometry Report', 'Motility Laboratory Note')
        item = proposal(run(text, [('91010', [ROW])]), '91010')
        self.assertEqual(item.status, 'needs_clarification')  # fail-closed: no documented study decides it


# A sigmoidoscopy whose band ligation is done through the sigmoidoscope.
BANDING = HEADER + """Flexible Sigmoidoscopy Procedure Note
Place of service: Physician office procedure room (POS 11)
Date of procedure: 2026-10-14
Endoscopist: Bo Lantern-Fictional, MD (fictional)
Sedation: None.

Indication
Bleeding from grade II internal hemorrhoids despite fiber.

Procedure
The flexible sigmoidoscope was advanced to 35 cm, in the sigmoid colon. The mucosa was normal. On retroflexion in the
rectum, grade II internal hemorrhoids were seen. Using a multi-band ligator mounted on the sigmoidoscope, one rubber band
was placed on the left lateral column and one on the right posterior column. No biopsies were taken.

Impression
Grade II internal hemorrhoids; band ligation of two columns through the flexible sigmoidoscope.
"""
ADVANCE = 'The flexible sigmoidoscope was advanced to 35 cm,'
LIGATION = 'band ligation of two columns through the flexible sigmoidoscope.'


class ActDocumentedInAnotherServiceTests(SimpleTestCase):
    """RC5: no service of the code's family is documented, and the act it accounts for is documented in another."""

    def test_the_catalogue_knows_the_act_of_an_unreconciled_code(self):
        self.assertEqual(catalogue.code_acts('46221'), ('band_ligation',))
        self.assertEqual(catalogue.code_acts('43239'), ('biopsy',))
        self.assertEqual(catalogue.code_acts('45378'), ())  # a base code accounts for the service itself
        self.assertEqual(catalogue.code_acts('99214'), ())
        self.assertEqual(catalogue.code_acts('46600'), ())  # not established: never guessed
        self.assertNotIn('46221', catalogue.CODES)  # never reconciled, never a coverage claim

    def test_its_passages_are_checked_against_the_act(self):
        result = run(BANDING, [('46221', ['Sedation: None.', ADVANCE])])
        item = proposal(result, '46221')
        support = check(item, 'evidence.support')
        self.assertIsNotNone(support, [c.id for c in item.checks])
        self.assertEqual(support.status, 'warn', support.detail)
        self.assertIn('band ligation', support.detail)
        self.assertEqual(item.support['unrelated'], [0, 1])
        self.assertTrue(any('multi-band ligator' in s['text'] for s in item.support['source']), item.support['source'])
        self.assertNotIn('service', item.support)  # never matched to the service that holds the act

    def test_the_service_that_holds_the_act_is_named(self):
        item = proposal(run(BANDING, [('46221', ['Sedation: None.', ADVANCE])]), '46221')
        placed = check(item, 'service.act_elsewhere')
        self.assertIsNotNone(placed, [c.id for c in item.checks])
        self.assertEqual(placed.status, 'warn')
        self.assertIn('flexible sigmoidoscopy', placed.detail)
        self.assertIn('sigmoidoscope', placed.detail)  # the act's own passage names it
        self.assertIn('no alternative is promoted', placed.detail)

    def test_nothing_is_added_promoted_or_held_by_it(self):
        result = run(BANDING, [('46221', ['Sedation: None.', ADVANCE])])
        self.assertEqual([p.code for p in result.proposals if p.bucket == 'selected'], ['46221'])
        item = proposal(result, '46221')
        self.assertEqual(item.status, 'ready')  # its own passages decide its status, as before
        self.assertEqual(item.clarifications, ())
        self.assertIn('gi.flex_sig', [u['family'] for u in result.completeness['unresolved_items']])

    def test_a_passage_that_shows_the_act_passes_and_the_service_is_still_named(self):
        item = proposal(run(BANDING, [('46221', [LIGATION])]), '46221')
        self.assertEqual(check(item, 'evidence.support').status, 'pass')
        self.assertIsNotNone(check(item, 'service.act_elsewhere'))

    def test_control_an_act_the_reader_reads_in_no_service_adds_nothing(self):
        text = HEADER + ('Anoscopy Procedure Note\nDate of procedure: 2026-10-14\nProcedure\nAn anoscope was inserted. '
                         'Grade II internal hemorrhoids were seen and two columns were banded with rubber bands.\n')
        item = proposal(run(text, [('46221', ['An anoscope was inserted.'])]), '46221')
        self.assertIsNone(check(item, 'evidence.support'))
        self.assertIsNone(check(item, 'service.act_elsewhere'))
        self.assertEqual(item.support, {})

    def test_control_an_act_done_through_another_instrument_is_never_placed_in_the_service(self):
        text = HEADER + ('Colonoscopy Report\nDate of service: 2026-10-14\nProcedure\nThe colonoscope was advanced to the '
                         'cecum. The colon was normal. After withdrawal of the colonoscope, an anoscope was inserted and '
                         'two internal hemorrhoids were banded.\n')
        item = proposal(run(text, [('46221', ['The colon was normal.'])]), '46221')
        self.assertIsNotNone(check(item, 'evidence.support'))  # the act is documented, so the passages are checked
        self.assertIsNone(check(item, 'service.act_elsewhere'))  # its passage never names the colonoscopy

    def test_control_a_code_of_the_documented_family_is_read_as_before(self):
        item = proposal(run(BANDING, [('45350', [LIGATION])]), '45350')
        self.assertIsNone(check(item, 'service.act_elsewhere'))
        self.assertEqual(check(item, 'evidence.support').status, 'pass')
        self.assertEqual(item.support['service'], 'S1')
