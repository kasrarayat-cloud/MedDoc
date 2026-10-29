"""GI round 2, fix round, lens "attr" (session 7c8d38da): the refutation of the attribution repair (3e4c258df).

Each finding is narrowed toward the installed reading (2b82889f) while the repair's intended gains stay (ho-08: 91010
ready, no phantom EGD; ho-09: 46221 with its support warning and the banding placed in the flexible sigmoidoscopy):

- attr-F1: the esophageal manometry name with its modifier after the organ ("esophageal high-resolution manometry") is
  read only as the title of the study's own report, never in prose, a field or a heading - in a clinic note's history it
  had made the manometry a performed service through the note's anoscopic banding, offered it for a second review and
  lost the office visit.
- attr-F2: a study act stays with its own study's service, as installed, where its report part, its sentence or the
  document's one procedure names that study, though the study is also named as planned or earlier elsewhere; it still
  never goes to another family's service.
- attr-F3: a passage of a study's own report shows that study only where the report reports no other study and the
  passage states no other act - never another study's result in a combined report, never an endoscopic biopsy.
- attr-F4: the document places an act in another service only where the act's own passage states it done through or
  with that service or its instrument - never "not through the flexible sigmoidoscope" or "after withdrawal of the
  colonoscope".
- attr-F5: an act documented in another family's service is checked against a code only at the code's own site - never
  an esophageal variceal ligation for a hemorrhoid banding code, or a gastric polypectomy for a colonoscopy code.

Every document is synthetic and written for this module; the expected outcome is written here, outside the coding
input. Nothing here asserts a code is right, only what the document documents and what the engine says about it.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect
from studio.gi import services as gi_services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


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


def services_of(inv, family):
    return [s for s in inv.services if s.family == family]


def performed(inv, family):
    return [s for s in services_of(inv, family) if s.status in ('performed', 'incomplete')]


def shown(inv):
    return [(s.family, s.status, [(a.kind, a.status) for a in s.acts]) for s in inv.services]


# --- attr-F1 ------------------------------------------------------------------------------------------------------

# An office visit whose history names an earlier manometry with the modifier after the organ, and whose only act today
# is an anoscopic banding.
CLINIC = HEADER + """Gastroenterology Clinic Note
Date of service: 2026-10-14
History of present illness
58-year-old established patient with achalasia diagnosed on esophageal high-resolution manometry in March 2025, now with
hemorrhoidal bleeding.
Examination
Abdomen soft and non-tender.
Procedure
Anoscopy was performed and two internal hemorrhoids were banded.
Assessment and plan
Internal hemorrhoids, banded. Fiber supplement.
"""
VISIT = '58-year-old established patient with achalasia'
ANOSCOPIC_BANDING = 'Anoscopy was performed and two internal hemorrhoids were banded.'

# The same name in other prose and field positions, each beside an act no study performs.
PROSE_POSITIONS = {
    'history without a hyphen': (
        HEADER + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\nHistory of present illness\n58-year-old with '
                 'achalasia diagnosed on esophageal high resolution manometry in March 2025, now with hemorrhoidal '
                 'bleeding.\nProcedure\n' + ANOSCOPIC_BANDING + '\nPlan\nFiber supplement.\n',
        [('46221', [ANOSCOPIC_BANDING])]),
    'a dated indication': (
        HEADER + 'Date of service: 2026-10-21\nIndication\nEsophageal high-resolution manometry on 2026-01-05 showed '
                 'type II achalasia.\nProcedure\nPneumatic dilation of the lower esophageal sphincter was performed with '
                 'a 30 mm balloon.\n',
        [('43249', ['Pneumatic dilation of the lower esophageal sphincter was performed with a 30 mm balloon.'])]),
    'a prior-studies table row': (
        HEADER + 'Clinic Procedure Note\nDate of service | 2026-10-14\nPrior studies | Esophageal high-resolution '
                 'manometry (03/2025): type II achalasia\nProcedure | Anoscopy; two internal hemorrhoid columns were '
                 'banded.\n',
        [('46221', ['Anoscopy; two internal hemorrhoid columns were banded.'])]),
    'a planned study': (
        HEADER + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\nHistory of present illness\n58-year-old '
                 'established patient with dysphagia and hemorrhoidal bleeding.\nProcedure\n' + ANOSCOPIC_BANDING
                 + '\nAssessment and plan\nInternal hemorrhoids, banded. Esophageal high-resolution manometry will be '
                   'scheduled for the dysphagia.\n',
        [('46221', [ANOSCOPIC_BANDING])]),
    'a title-case line under prior studies': (
        HEADER + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\nPrior studies\nEsophageal High-Resolution '
                 'Manometry (2025): type II achalasia.\nHistory of present illness\n58-year-old established patient '
                 'with hemorrhoidal bleeding.\nProcedure\n' + ANOSCOPIC_BANDING + '\nAssessment and plan\nInternal '
                 'hemorrhoids, banded.\n',
        [('46221', [ANOSCOPIC_BANDING])]),
}

# The study's own report, titled with the modifier after the organ (ho-08's shape).
HRM = HEADER + """Esophageal High-Resolution Manometry Report
Date of service: 2026-10-13
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
Type II achalasia by Chicago Classification version 4.0.
Recommendations
Treatment options are peroral endoscopic myotomy or pneumatic dilation.
"""
ROW = 'Median integrated relaxation pressure (mmHg) | 27.9 | 23.0'
READING = 'Type II achalasia by Chicago Classification version 4.0.'


class WidenedStudyNameIsReadOnlyAsItsReportTitleTests(SimpleTestCase):
    """attr-F1: the widened name never documents a study from prose; the installed reading stands there."""

    def test_a_history_sentence_naming_the_study_documents_no_study_and_keeps_the_visit(self):
        inv = inventory(CLINIC)
        self.assertEqual(services_of(inv, 'gi.motility'), [], shown(inv))
        self.assertEqual(len(performed(inv, 'gi.office_em')), 1, shown(inv))
        result = run(CLINIC, [('99213', [VISIT]), ('46221', [ANOSCOPIC_BANDING])])
        visit = proposal(result, '99213')
        self.assertEqual(check(visit, 'service.status').status, 'pass', check(visit, 'service.status').detail)
        self.assertNotIn('performed_status', [c.fact for c in visit.clarifications])
        unresolved = result.completeness['unresolved_items']
        self.assertEqual([u for u in unresolved if u['family'] == 'gi.motility'], [])
        self.assertEqual([u for u in unresolved if u.get('second_review')], [])

    def test_no_prose_or_field_position_of_the_widened_name_documents_a_study(self):
        for name, (text, codes) in PROSE_POSITIONS.items():
            with self.subTest(name):
                inv = inventory(text)
                self.assertEqual(services_of(inv, 'gi.motility'), [], shown(inv))
                result = run(text, codes)
                self.assertEqual([u for u in result.completeness['unresolved_items'] if u['family'] == 'gi.motility'],
                                 [])

    def test_a_report_title_of_another_occurrence_documents_no_study(self):
        cases = {
            'under prior studies': HEADER + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\nPrior studies:\n'
                                            'Esophageal High-Resolution Manometry Report\nType II achalasia in 2025.\n'
                                            'History of present illness\n58-year-old established patient with '
                                            'hemorrhoidal bleeding.\nProcedure\n' + ANOSCOPIC_BANDING + '\n',
            'dated before the service date': HEADER + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\n'
                                                      '2025-03-02 Esophageal High-Resolution Manometry Report\nType II '
                                                      'achalasia.\nProcedure\n' + ANOSCOPIC_BANDING + '\n',
        }
        for name, text in cases.items():
            with self.subTest(name):
                inv = inventory(text)
                self.assertEqual(performed(inv, 'gi.motility'), [], shown(inv))
                result = run(text, [('46221', [ANOSCOPIC_BANDING])])
                self.assertEqual([u for u in result.completeness['unresolved_items'] if u['family'] == 'gi.motility'],
                                 [])

    def test_control_the_widened_name_still_titles_the_study_s_own_report(self):
        self.assertEqual(gi_services._family_named('Esophageal High-Resolution Manometry Report')[0], 'gi.motility')
        motility = performed(inventory(HRM), 'gi.motility')
        self.assertEqual(len(motility), 1)
        self.assertTrue(any(a.kind == 'manometry' and a.status == 'performed' for a in motility[0].acts))
        item = proposal(run(HRM, [('91010', [ROW, READING])]), '91010')
        self.assertEqual(item.status, 'ready', [(c.id, c.status, c.detail) for c in item.checks])


# --- attr-F2 ------------------------------------------------------------------------------------------------------

def lab_note(title, earlier_heading, earlier, technique_heading, act, tail=''):
    return (HEADER + f'{title}\nDate of service: 2026-10-14\n{earlier_heading}\n{earlier}\n{technique_heading}\n{act}\n'
            + tail)


MANOMETRY_ACT = 'A manometry catheter was placed through the nose and ten swallows were recorded.'
RESULTS = 'Results\nMedian IRP (mmHg) | 27\nInterpretation\nType II achalasia.\n'
REFLUX_ACT = 'A pH-impedance catheter was placed through the nose and recording was started.'
OWN_STUDY_NAMED_ELSEWHERE = {
    # (text, code, the study's family)
    'an earlier manometry in the history': (
        lab_note('Motility Laboratory Note', 'History', 'Esophageal manometry in 2024 was normal.', 'Technique',
                 MANOMETRY_ACT, RESULTS), '91010', 'gi.motility'),
    'a repeat pH study in the plan': (
        HEADER + 'Reflux Laboratory Note\nDate of service: 2026-10-14\nProcedure\n' + REFLUX_ACT
        + '\nPlan\nRepeat 24-hour pH-impedance monitoring off PPI in three months.\n', '91037', 'gi.reflux'),
    'a repeat manometry in the recommendations': (
        HEADER + 'High-Resolution Manometry Report\nDate of service: 2026-10-14\nTechnique\nA solid-state manometry '
                 'catheter was placed transnasally. Ten swallows were given.\n' + RESULTS
        + 'Recommendations\nRepeat esophageal manometry after treatment.\n', '91010', 'gi.motility'),
    'a prior-studies label': (
        HEADER + 'Motility Laboratory Note\nDate of service: 2026-10-14\nPrior studies: esophageal manometry (2024) '
                 'normal.\nProcedure: A manometry catheter was placed transnasally and ten wet swallows were '
                 'recorded.\nResults: Median IRP (mmHg) | 27\nImpression: Type II achalasia.\n', '91010', 'gi.motility'),
}


class StudyActStaysWithItsOwnStudyTests(SimpleTestCase):
    """attr-F2: a study done today keeps its own act though its family is also named as planned or earlier."""

    def test_the_study_act_documents_its_own_study_named_only_as_earlier_elsewhere(self):
        text, code, family = OWN_STUDY_NAMED_ELSEWHERE['an earlier manometry in the history']
        inv = inventory(text)
        study = performed(inv, family)
        self.assertEqual(len(study), 1, shown(inv))
        self.assertTrue(any(a.kind == 'manometry' and a.status == 'performed' for a in study[0].acts), shown(inv))
        item = proposal(run(text, [(code, [MANOMETRY_ACT])]), code)
        self.assertEqual(item.status, 'ready', [(c.id, c.status, c.detail) for c in item.checks])
        self.assertEqual(check(item, 'service.status').status, 'pass')
        self.assertEqual(check(item, 'evidence.support').status, 'pass')

    def test_each_study_named_as_planned_or_earlier_elsewhere_keeps_its_act(self):
        for name, (text, code, family) in OWN_STUDY_NAMED_ELSEWHERE.items():
            with self.subTest(name):
                inv = inventory(text)
                self.assertEqual(len(performed(inv, family)), 1, shown(inv))
                act = next(line for line in text.split('\n') if 'catheter was placed' in line).split(': ', 1)[-1]
                item = proposal(run(text, [(code, [act])]), code)
                self.assertEqual(item.status, 'ready', [(c.id, c.status, c.detail) for c in item.checks])
                self.assertNotIn('performed_status', [c.fact for c in item.clarifications])

    def test_a_widened_name_in_a_recommendation_holds_no_study_done_today(self):
        text = (HEADER + 'Manometry Report\nDate of service: 2026-10-14\nTechnique\nA solid-state catheter was placed '
                         'transnasally and ten wet swallows were recorded.\nInterpretation\nType II achalasia.\n'
                         'Recommendation\nRepeat esophageal high-resolution manometry after myotomy.\n')
        item = proposal(run(text, [('91010', ['A solid-state catheter was placed transnasally and ten wet swallows were '
                                              'recorded.', 'Type II achalasia.'])]), '91010')
        self.assertEqual(item.status, 'ready', [(c.id, c.status, c.detail) for c in item.checks])

    def test_control_a_study_act_still_never_joins_another_study(self):
        text = (HEADER + 'Wireless pH Monitoring Report\nDate of service: 2026-10-14\nTechnique\nA wireless pH capsule '
                         'was attached 6 cm above the squamocolumnar junction, located by high-resolution manometry '
                         'performed on 2026-09-28 (separate study, reported previously).\nFindings\nAcid exposure time '
                         '7.1 percent.\n')
        inv = inventory(text)
        self.assertEqual([a.kind for s in services_of(inv, 'gi.reflux') for a in s.acts if a.kind == 'manometry'], [],
                         shown(inv))


# --- attr-F3 ------------------------------------------------------------------------------------------------------

def combined(title):
    return (HEADER + f'{title}\nDate of service: 2026-10-14\nTechnique\nA manometry catheter was placed through the '
                     'nose; then a pH-impedance catheter was placed for 24 hours.\nFindings\nMedian IRP 9 mmHg; normal '
                     'peristalsis.\nAcid exposure time 8.2 percent; DeMeester score 31.\nImpression\nNormal motility; '
                     'pathologic acid reflux.\n')


MANOMETRY_RESULT = 'Median IRP 9 mmHg; normal peristalsis.'
PH_RESULT = 'Acid exposure time 8.2 percent; DeMeester score 31.'


class OwnReportShowsOnlyItsOwnStudyTests(SimpleTestCase):
    """attr-F3: another study's result, or another act, in a report never shows the study."""

    def test_another_study_s_result_in_a_combined_report_never_shows_the_study(self):
        for title in ('Esophageal Manometry and 24-Hour pH-Impedance Report',
                      '24-Hour pH-Impedance and Esophageal Manometry Report'):
            with self.subTest(title):
                result = run(combined(title), [('91010', [PH_RESULT]), ('91037', [MANOMETRY_RESULT])])
                for code in ('91010', '91037'):
                    support = check(proposal(result, code), 'evidence.support')
                    self.assertEqual(support.status, 'warn', (code, support.detail))

    def test_a_combined_report_s_rows_never_show_the_other_study(self):
        text = (HEADER + 'Esophageal Manometry and 24-Hour pH-Impedance Report\nDate of service: 2026-10-14\nTechnique\n'
                         'A manometry catheter was placed through the nose; then a pH-impedance catheter was placed for '
                         '24 hours.\nFindings\nMedian IRP (mmHg) | 9\nPeristalsis | normal\nAcid exposure time (%) | 8.2\n'
                         'DeMeester score | 31\nImpression\nNormal motility; pathologic acid reflux.\n')
        result = run(text, [('91010', ['DeMeester score | 31']), ('91037', ['Median IRP (mmHg) | 9'])])
        for code in ('91010', '91037'):
            self.assertEqual(check(proposal(result, code), 'evidence.support').status, 'warn', code)

    def test_a_report_titled_for_one_study_that_records_another_is_no_own_report_of_either(self):
        result = run(combined('Esophageal Manometry Report'), [('91010', [PH_RESULT])])
        support = check(proposal(result, '91010'), 'evidence.support')
        self.assertEqual(support.status, 'warn', support.detail)

    def test_an_endoscopic_act_in_the_study_s_report_never_shows_the_study(self):
        report = (HEADER + 'Esophageal High-Resolution Manometry Report\nDate of service: 2026-10-14\nTechnique\nA '
                           'manometry catheter was placed through the nose.\nFindings\nMedian IRP 27 mmHg; failed '
                           'peristalsis in 10 of 10 swallows.\n{findings}Impression\nType II achalasia.\n{addendum}')
        cases = {
            'findings': report.format(findings='Biopsies of the distal esophagus were taken.\n', addendum=''),
            'addendum': report.format(findings='', addendum='Addendum\nFindings\nAfter the study a 4 cm hiatal hernia was '
                                                            'seen and biopsies of the distal esophagus were taken.\n'),
        }
        for name, text in cases.items():
            with self.subTest(name):
                cited = next(line for line in text.split('\n') if 'biopsies of the distal' in line.lower())
                support = check(proposal(run(text, [('91010', [cited])]), '91010'), 'evidence.support')
                self.assertIsNotNone(support)
                self.assertEqual(support.status, 'warn', support.detail)

    def test_a_passage_longer_than_one_read_sentence_shows_nothing_by_its_place(self):
        rows = ''.join(f'Swallow {n} | failed peristalsis | IRP (mmHg) | 27\n' for n in range(1, 41))
        text = (HEADER + 'Esophageal High-Resolution Manometry Report\nDate of service: 2026-10-14\nTechnique\nA '
                         'manometry catheter was placed through the nose.\nFindings\n' + rows + 'Impression\nType II '
                         'achalasia.\n')
        cited = rows.rstrip('\n')
        self.assertGreater(len(cited), gi_services.SENTENCE_READ_CHARS)
        support = check(proposal(run(text, [('91010', [cited])]), '91010'), 'evidence.support')
        self.assertEqual(support.status, 'warn', support.detail)

    def test_control_the_single_study_report_s_results_still_show_it(self):
        item = proposal(run(HRM, [('91010', [ROW, READING])]), '91010')
        self.assertEqual(check(item, 'evidence.support').status, 'pass')
        self.assertEqual(check(item, 'service.status').status, 'pass')


# --- attr-F4 ------------------------------------------------------------------------------------------------------

SIGMOIDOSCOPY = HEADER + 'Flexible Sigmoidoscopy Report\nDate of service: 2026-10-14\nProcedure\nThe flexible sigmoidoscope was ' \
                         'advanced to 40 cm. {act}\n'
COLONOSCOPY = HEADER + 'Colonoscopy Report\nDate of service: 2026-10-14\nProcedure\nThe colonoscope was advanced to the ' \
                       'cecum. The colon was normal. {act}\n'


class PlacementNeedsTheActDoneThroughTheServiceTests(SimpleTestCase):
    """attr-F4: an act is placed in a service only where its own passage states it done through or with it."""

    def test_an_act_its_passage_says_was_not_done_through_the_service_is_never_placed_in_it(self):
        cases = {
            'not through': (SIGMOIDOSCOPY, 'Hemorrhoids were banded with the anoscope, not through the flexible '
                                           'sigmoidoscope.', None),
            'after withdrawal': (COLONOSCOPY, 'Two internal hemorrhoids were banded with an anoscope after withdrawal of '
                                              'the colonoscope.', None),
            'after removal': (COLONOSCOPY, 'After the colonoscope was removed, two internal hemorrhoids were banded '
                                           'using an anoscope.', None),
            'instead of through': (COLONOSCOPY, 'Internal hemorrhoids were banded via anoscopy instead of through the '
                                                'colonoscope.', None),
            'another passage cited': (COLONOSCOPY, 'Two internal hemorrhoids were banded with an anoscope after '
                                                   'withdrawal of the colonoscope.', 'The colon was normal.'),
            'the instrument heading another phrase': (COLONOSCOPY, 'With the colonoscope withdrawn, two internal '
                                                                   'hemorrhoids were banded using an anoscope.', None),
        }
        for name, (template, act, cited) in cases.items():
            with self.subTest(name):
                item = proposal(run(template.format(act=act), [('46221', [cited or act])]), '46221')
                self.assertIsNone(check(item, 'service.act_elsewhere'), [(c.id, c.detail) for c in item.checks])

    def test_control_an_act_done_through_or_with_the_service_s_instrument_is_placed_in_it(self):
        cases = {
            'through the sigmoidoscope': (SIGMOIDOSCOPY, 'Band ligation of two columns of internal hemorrhoids was '
                                                         'performed through the flexible sigmoidoscope.',
                                          'flexible sigmoidoscopy'),
            'through the colonoscope': (COLONOSCOPY, 'On retroflexion two internal hemorrhoids were banded through the '
                                                     'colonoscope.', 'colonoscopy'),
            'with the colonoscope': (COLONOSCOPY, 'Internal hemorrhoids were banded today with the colonoscope in '
                                                  'retroflexion.', 'colonoscopy'),
        }
        for name, (template, act, service) in cases.items():
            with self.subTest(name):
                item = proposal(run(template.format(act=act), [('46221', [act])]), '46221')
                placed = check(item, 'service.act_elsewhere')
                self.assertIsNotNone(placed, [(c.id, c.detail) for c in item.checks])
                self.assertEqual(placed.status, 'warn')
                self.assertIn(f'the documented {service}', placed.detail)
                self.assertEqual(check(item, 'evidence.support').status, 'pass')


# --- attr-F5 ------------------------------------------------------------------------------------------------------

EGD = HEADER + 'EGD Report\nDate of service: 2026-10-14\nProcedure\nThe gastroscope was advanced to the second portion of ' \
               'the duodenum. {act}\n'
VARICES = 'Four bands were placed on grade III esophageal varices.'


class ElsewhereCountsOnlyTheCodesOwnSiteTests(SimpleTestCase):
    """attr-F5: an act documented in another family's service is checked against a code only at the code's own site."""

    def test_an_act_at_another_site_is_never_checked_against_the_code(self):
        cases = {
            'variceal banding for a hemorrhoid banding code': (EGD.format(act=VARICES), [('46221', [VARICES])], '46221'),
            'gastric polypectomy for a colonoscopy code': (
                EGD.format(act='A 12 mm gastric polyp was removed by hot snare polypectomy.'),
                [('45385', ['A 12 mm gastric polyp was removed by hot snare polypectomy.'])], '45385'),
            'variceal banding beside its own code': (EGD.format(act=VARICES), [('46221', [VARICES]), ('43244', [VARICES])],
                                                     '46221'),
            'a banding of no stated site in an upper endoscopy': (
                EGD.format(act='Four bands were placed.'), [('46221', ['Four bands were placed.'])], '46221'),
        }
        for name, (text, codes, code) in cases.items():
            with self.subTest(name):
                item = proposal(run(text, codes), code)
                self.assertIsNone(check(item, 'evidence.support'), [(c.id, c.status, c.detail) for c in item.checks])
                self.assertIsNone(check(item, 'service.act_elsewhere'))
                self.assertEqual(item.support, {})

    def test_control_an_act_at_the_code_s_own_site_is_still_checked(self):
        biopsy = 'Cold forceps biopsies of the sigmoid colon were taken.'
        item = proposal(run(COLONOSCOPY.format(act=biopsy), [('45331', [biopsy])]), '45331')
        self.assertEqual(check(item, 'evidence.support').status, 'pass')
        banding = 'Band ligation of two columns of internal hemorrhoids was performed through the flexible sigmoidoscope.'
        item = proposal(run(SIGMOIDOSCOPY.format(act=banding), [('46221', ['The flexible sigmoidoscope was advanced to '
                                                                           '40 cm.'])]), '46221')
        self.assertEqual(check(item, 'evidence.support').status, 'warn')
        self.assertIsNotNone(check(item, 'service.act_elsewhere'))
