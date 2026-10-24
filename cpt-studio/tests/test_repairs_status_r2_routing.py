"""Regressions for refutation round 2 over GI routing (round "2b").

Round 2 attacked the round-1 routing repairs from both sides, and each class here
reproduces one confirmed finding (status:N in the round-2 triage) from its exact
input, adds the wordings the finding lists, and pins positive controls:

- over-correction: an ordinary, clearly performed procedure is excluded or held;
- under-correction: a service that was not performed still becomes a ready code.

Routing runs for real, for the document's own service date and through the JSON
round trip the pipeline applies; the real validation engine assesses
provider-shaped selections against an empty in-memory reference. Synthetic text
only.
"""
import json
import unittest
from datetime import date
from pathlib import Path

from studio.gi import detect
from studio.gi.context import extract_context
from studio.gi.detect import route, status_for_span
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, RoutingResult, from_jsonable,
                          to_jsonable)
from studio.validation.engine import assess

HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
DOCS = Path(__file__).resolve().parent.parent / 'ops' / 'verification' / 'documents'
NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')
POSITIVE = ('performed', 'incomplete')
SILENT = 'uncertain: no performance evidence'


def doc(name):
    return next(DOCS.glob(f'{name}-*.txt')).read_text(encoding='utf-8')


def span(text, phrase, occurrence=0):
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(phrase, start + 1)
    return start, start + len(phrase)


def service_date(text):
    fact = extract_context(text)['service_date']
    return date.fromisoformat(fact.value) if fact.origin == 'document' and fact.value else None


def routed(text):
    """Routing as the pipeline stores it: for the document's own date, through JSON and back."""
    result = route(text, service_date(text))
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(result))))


def read(text, phrase, occurrence=0):
    return status_for_span(text, *span(text, phrase, occurrence), service_date(text))


def family(text, slug):
    finding = routed(text).finding(slug)
    return finding.status if finding else None


def fact_value(text, slug, name):
    finding = routed(text).finding(slug)
    return next((f.value for f in (finding.facts if finding else ()) if f.name == name), None)


def run_engine(text, picks):
    """picks: (code, evidence phrase[, occurrence]). The proposals by code, and the whole result."""
    codes = []
    for index, pick in enumerate(picks):
        start, end = span(text, pick[1], pick[2] if len(pick) > 2 else 0)
        codes.append(ProviderCode(role='selected', system='cpt', code=pick[0], display='UNVERIFIED',
                                  evidence=(EvidenceSpan(0, start, end, text[start:end], True),), index=index))
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text), routing=routed(text),
                    normalized=NormalizedResponse('replay', 'test', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=service_date(text),
                    provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals}, result


def check(proposal, check_id):
    return next((c for c in proposal.checks if c.id == check_id), None)


def clarified(proposal):
    return [c.fact for c in proposal.clarifications]


class VersionTests(unittest.TestCase):
    def test_the_routing_version_is_bumped_once(self):
        self.assertEqual(detect.ROUTING_VERSION, 'gi-routing@3')


GI03_LINE = 'Colonoscopy with cold snare polypectomy and cold forceps biopsy.'
GI03_SNARE = 'were each removed completely with a cold snare and retrieved (jar A)'
GI03_FORCEPS = 'was sampled with cold forceps biopsy for histology (jar B)'
POLYPS = 'Two 4 mm polyps in the transverse colon were removed with a cold snare.'


def colon_with_plan(line, plan='Plan: Repeat colonoscopy in 5 years.\n', between=''):
    return (HEADER + f'Procedure: {line}\n{between}Findings: The colonoscope was advanced to the cecum. {POLYPS}\n'
            + plan)


EGD_C = (HEADER + 'Procedure: EGD to evaluate dysphagia.\nIndication: Dysphagia. A prior EGD in 2023 was normal.\n'
         'Findings: The gastroscope was advanced to the second part of the duodenum. A Schatzki ring was dilated with '
         'an 18 mm balloon. Biopsies were taken from the mid esophagus.\n')
EGD_PICKS = [('43249', 'A Schatzki ring was dilated with an 18 mm balloon.'),
             ('43239', 'Biopsies were taken from the mid esophagus.')]


class Status0NoCascadeIntoExclusionTests(unittest.TestCase):
    """status:0 - doubt about today's service, a routine plan line or a negation about earlier
    encounters never cascades into excluding the family's performed codes as planned,
    historical or negated, for the family or for its other passages."""

    def test_case_a_gi03_with_a_purpose_in_its_procedure_line(self):
        original = doc('gi-03')
        text = original.replace(GI03_LINE, 'Colonoscopy to screen for colorectal cancer, with cold snare polypectomy '
                                           'and cold forceps biopsy.')
        self.assertNotEqual(text, original)
        self.assertNotIn(family(text, 'gi.colonoscopy'), NOT_TODAY)
        title = next(m for m in routed(text).finding('gi.colonoscopy').mentions if m.section == 'procedure')
        self.assertNotEqual(title.status, 'negated', title.cues)
        self.assertFalse(any(cue.startswith('negated: No prior') for cue in title.cues), title.cues)
        proposals, _ = run_engine(text, [('45385', GI03_SNARE), ('45380', GI03_FORCEPS)])
        for code in ('45385', '45380'):
            with self.subTest(code=code):
                self.assertEqual(proposals[code].bucket, 'selected', proposals[code].exclusion_reason)

    def test_case_b_ordinary_procedure_lines_beside_a_routine_plan(self):
        for line in ('Colonoscopy to evaluate iron deficiency anemia.', 'Colonoscopy on 2026-10-21.',
                     'Colonoscopy/polypectomy.', 'Colonoscopy, average-risk screening.', 'Colonoscopy\nPatient not sedated.'):
            text = colon_with_plan(line)
            with self.subTest(line=line):
                self.assertNotIn(family(text, 'gi.colonoscopy'), NOT_TODAY)
                proposals, _ = run_engine(text, [('45385', POLYPS)])
                self.assertEqual(proposals['45385'].bucket, 'selected', proposals['45385'].exclusion_reason)

    def test_case_c_egd_to_evaluate_beside_a_dated_prior_egd(self):
        self.assertNotIn(family(EGD_C, 'gi.egd'), NOT_TODAY)
        proposals, _ = run_engine(EGD_C, EGD_PICKS)
        for code in ('43249', '43239'):
            with self.subTest(code=code):
                self.assertEqual(proposals[code].bucket, 'selected', proposals[code].exclusion_reason)

    def test_a_genuine_doubt_is_held_never_excluded(self):
        """The structural rule on lines that stay doubtful: uncertain family, held code."""
        for line in ('Colonoscopy - TBD.', 'Colonoscopy requested.', 'Colonoscopy?'):
            text = colon_with_plan(line, between='Indication: Screening. No prior colonoscopy.\n')
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
                status, cues = read(text, POLYPS)
                self.assertEqual(status, 'uncertain', cues)
                self.assertFalse(any(c.startswith(('planned:', 'historical:', 'negated:')) for c in cues), cues)
                proposals, _ = run_engine(text, [('45385', POLYPS)])
                self.assertEqual((proposals['45385'].bucket, proposals['45385'].status),
                                 ('selected', 'needs_clarification'))
                self.assertIn('performed_status', clarified(proposals['45385']))

    def test_routine_plan_lines_never_override_todays_procedure(self):
        """A negation or a doubt in a plan section speaks of the plan, not of today's service."""
        for plan in ('Plan: No further colonoscopy is needed for 10 years.\n', 'Plan: Colonoscopy not needed for 10 '
                     'years.\n', 'Plan: Repeat colonoscopy pending pathology.\n', 'Plan: Repeat colonoscopy in 5 years.\n',
                     'Recommendations: No surveillance colonoscopy is required.\n'):
            text = colon_with_plan('Colonoscopy with cold snare polypectomy.', plan=plan)
            with self.subTest(plan=plan):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                proposals, _ = run_engine(text, [('45385', POLYPS)])
                self.assertEqual((proposals['45385'].bucket, proposals['45385'].status), ('selected', 'ready'))

    def test_a_past_negation_never_decides_a_family_with_a_reading_about_today(self):
        text = colon_with_plan('Colonoscopy - TBD.', plan='', between='Indication: No prior colonoscopy.\n')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')
        self.assertEqual(read(text, 'No prior colonoscopy.')[0], 'negated')  # the mention reads as the negation it is

    def test_no_history_plan_or_past_negation_is_stamped_on_a_performed_passage(self):
        """A family named only as historical, planned or never done before: its unnamed performed
        passage is held for clarification, never excluded as that other status."""
        for lead, plan in (('Indication: Prior colonoscopy in 2020.\n', ''),
                           ('Indication: Screening. No prior colonoscopy.\n', ''),
                           ('', 'Plan: Repeat colonoscopy in 5 years.\n')):
            text = (HEADER + lead + f'Findings: The colonoscope was advanced to the cecum. {POLYPS}\n' + plan)
            with self.subTest(lead=lead, plan=plan):
                status, cues = read(text, POLYPS)
                self.assertNotIn(status, NOT_TODAY, cues)
                self.assertFalse(any(c.startswith(('planned:', 'historical:', 'negated:')) for c in cues[1:]), cues)
                proposals, _ = run_engine(text, [('45385', POLYPS)])
                self.assertEqual(proposals['45385'].bucket, 'selected', proposals['45385'].exclusion_reason)
                self.assertNotEqual(proposals['45385'].status, 'ready')

    def test_a_negation_of_todays_service_still_negates(self):
        """The family is negated; the section-read line it denies is held, not rewritten as negated."""
        text = HEADER + 'Procedure: Colonoscopy\nNo colonoscopy was performed; the patient left before sedation.\n'
        self.assertEqual(family(text, 'gi.colonoscopy'), 'negated')
        status, cues = read(text, 'Colonoscopy')
        self.assertEqual(status, 'uncertain', cues)
        proposals, _ = run_engine(text, [('45378', 'Colonoscopy')])
        self.assertEqual((proposals['45378'].bucket, proposals['45378'].status), ('selected', 'needs_clarification'))

    def test_a_plan_or_history_line_about_today_still_contradicts(self):
        for line in ('Plan: No colonoscopy was performed today because of poor preparation; reschedule.\n',
                     'History: Colonoscopy was not performed today.\n'):
            text = HEADER + 'Procedure: Colonoscopy\n' + line
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'negated')

    def test_silence_does_not_outrank_a_plan_or_a_history(self):
        for body, expected in (('Assessment: Reflux; EGD.\nPlan: EGD next week.\n', 'planned'),
                               ('Assessment: Reflux; EGD.\nHistory: EGD in 2019 was normal.\n', 'historical')):
            with self.subTest(body=body):
                self.assertEqual(family(HEADER + body, 'gi.egd'), expected)

    def test_unproven_section_evidence_is_about_today(self):
        """An office note's procedure heading without extent or interventions holds the family as
        uncertain whatever a history line says."""
        text = (HEADER + 'Office visit.\nChief complaint\nReflux.\nProcedures\nColonoscopy (normal).\nHistory\nPrior '
                'colonoscopy in 2019.\nMedical decision making\nLow.\n')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'uncertain')


STATUS1 = ('SYNTHETIC TEST NOTE - NOT A REAL PATIENT\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\n'
           'Established patient office visit for rectal bleeding.\nHistory of present illness: Two weeks of intermittent '
           'bright red blood per rectum. Prior flexible sigmoidoscopy in 2022 was normal.\nProcedure: Flexible '
           'sigmoidoscopy to evaluate rectal bleeding.\nFindings: The sigmoidoscope was advanced to 40 cm. A biopsy was '
           'taken from the rectum.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
STATUS1_PICKS = [('99214', 'Established patient office visit for rectal bleeding.'),
                 ('45331', 'A biopsy was taken from the rectum.')]


class Status1EmHoldSurvivesTests(unittest.TestCase):
    """status:1 - the same cascade no longer releases the same-day E/M hold."""

    def assert_held_beside_a_kept_procedure(self, text):
        proposals, _ = run_engine(text, STATUS1_PICKS)
        self.assertEqual(proposals['45331'].bucket, 'selected', proposals['45331'].exclusion_reason)
        visit = proposals['99214']
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', clarified(visit))
        self.assertIsNotNone(check(visit, 'em.same_day_procedure'))

    def test_the_claimed_input(self):
        self.assertNotIn(family(STATUS1, 'gi.flex_sig'), NOT_TODAY)
        self.assert_held_beside_a_kept_procedure(STATUS1)

    def test_a_dated_history_cue_is_never_attached_to_todays_sentence(self):
        status, cues = read(STATUS1, 'A biopsy was taken from the rectum.')
        self.assertNotIn(status, NOT_TODAY, cues)
        self.assertFalse(any('2022' in cue for cue in cues), cues)

    def test_the_variants(self):
        history = 'Prior flexible sigmoidoscopy in 2022 was normal.'
        for old, new in ((history, '\nPast surgical history: flexible sigmoidoscopy 2019.'),
                         (history, 'No other complaints.'),
                         ('Medical decision making', 'Plan: Repeat flexible sigmoidoscopy in 3 years.\nMedical decision '
                                                     'making')):
            text = STATUS1.replace(old, new, 1)
            with self.subTest(new=new):
                self.assertNotEqual(text, STATUS1)
                self.assert_held_beside_a_kept_procedure(text)


def ready(proposal):
    return (proposal.bucket, proposal.status) == ('selected', 'ready')


class Status2OrdinaryProcedureLinesTests(unittest.TestCase):
    """status:2 - a purpose, a date, a place, a joiner (' | ', '/', '+') or a descriptive word after
    the service name is part of an ordinary procedure line: performed family, ready codes, kept facts."""

    def test_gi02_with_a_purpose_clause(self):
        original = doc('gi-02')
        text = original.replace('Esophagogastroduodenoscopy (EGD) with cold forceps biopsy.',
                                'Esophagogastroduodenoscopy (EGD) to evaluate epigastric pain, with cold forceps biopsy.')
        self.assertNotEqual(text, original)
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        proposals, _ = run_engine(text, [('43239', 'Two cold forceps biopsies were taken from the gastric antrum for '
                                                   'histology and Helicobacter pylori assessment.')])
        self.assertTrue(ready(proposals['43239']), proposals['43239'].clarifications)

    def test_gi10_with_a_purpose_clause(self):
        original = doc('gi-10')
        text = original.replace('Endoscopic retrograde cholangiopancreatography (ERCP) with biliary sphincterotomy and '
                                'balloon extraction of common bile duct stones.',
                                'ERCP to remove common bile duct stones, with biliary sphincterotomy and balloon '
                                'extraction.')
        self.assertNotEqual(text, original)
        pick = [('43262', 'A biliary sphincterotomy of moderate size was performed with blended current.')]
        self.assertEqual(family(text, 'gi.ercp'), family(original, 'gi.ercp'))
        self.assertEqual(family(text, 'gi.ercp'), 'performed')
        self.assertTrue(ready(run_engine(text, pick)[0]['43262']))

    def test_eus_purpose_clause_keeps_its_target(self):
        text = (HEADER + 'Procedure: EUS to evaluate a pancreatic head mass.\nTechnique: The linear echoendoscope was '
                'advanced to the second part of the duodenum.\nFindings: A 24 mm hypoechoic mass was seen in the '
                'pancreatic head. Fine-needle biopsy (FNB) was performed with a 22-gauge needle using three passes.\n')
        self.assertEqual(family(text, 'gi.eus'), 'performed')
        self.assertEqual(fact_value(text, 'gi.eus', 'target'), 'pancreatic head mass')
        proposals, _ = run_engine(text, [('43242', 'Fine-needle biopsy (FNB) was performed with a 22-gauge needle using '
                                                   'three passes.')])
        self.assertTrue(ready(proposals['43242']), proposals['43242'].clarifications)

    def test_docx_table_rows(self):
        text = (HEADER + 'Procedures performed:\nColonoscopy | Performed | Cecum reached, 2 polyps removed\nFindings: '
                'The colonoscope was advanced to the cecum. Two polyps were removed with a cold snare.\n')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertTrue(ready(run_engine(text, [('45385', 'Two polyps were removed with a cold snare.')])[0]['45385']))
        denied = HEADER + 'Procedures performed:\nColonoscopy | Not performed | Patient declined\n'
        self.assertEqual(family(denied, 'gi.colonoscopy'), 'negated')

    def test_status0_and_status1_inputs_are_ready(self):
        text = doc('gi-03').replace(GI03_LINE, 'Colonoscopy to screen for colorectal cancer, with cold snare polypectomy '
                                               'and cold forceps biopsy.')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        proposals, _ = run_engine(text, [('45385', GI03_SNARE), ('45380', GI03_FORCEPS)])
        self.assertTrue(ready(proposals['45385']) and ready(proposals['45380']))
        for line in ('Colonoscopy to evaluate iron deficiency anemia.', 'Colonoscopy on 2026-10-21.',
                     'Colonoscopy/polypectomy.', 'Colonoscopy, average-risk screening.'):
            text = colon_with_plan(line)
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assertTrue(ready(run_engine(text, [('45385', POLYPS)])[0]['45385']))
        self.assertEqual(family(EGD_C, 'gi.egd'), 'performed')
        proposals, _ = run_engine(EGD_C, EGD_PICKS)
        self.assertTrue(ready(proposals['43249']) and ready(proposals['43239']))
        self.assertEqual(family(STATUS1, 'gi.flex_sig'), 'performed')
        proposals, _ = run_engine(STATUS1, STATUS1_PICKS)
        self.assertTrue(ready(proposals['45331']))
        self.assertIn('separate_em', clarified(proposals['99214']))

    def test_ordinary_lines_read_performed_under_a_procedure_heading(self):
        for line in ('Colonoscopy for evaluation of rectal bleeding.', 'Colonoscopy to evaluate rectal bleeding.',
                     'Colonoscopy on 2026-10-21.', 'Colonoscopy at Harborview Endoscopy Center.',
                     'Colonoscopy, average-risk screening.', 'Colonoscopy + polypectomy.', 'Colonoscopy/polypectomy.',
                     'Colonoscopy due to iron deficiency anemia.', 'Colonoscopy prior to surgery.',
                     'Colonoscopy | Diagnostic | Biopsies taken',
                     'Colonoscopy, screening, with cold snare polypectomy of a 6 mm polyp that was retrieved.',
                     'Colonoscopy with biopsy of a lesion of uncertain significance.',
                     'Colonoscopy with cold snare polypectomy, pathology pending.',
                     'Colonoscopy with biopsy of a suspected adenoma at the previously tattooed site.',
                     'Colonoscopy with polypectomy of a polyp detected on CT.',
                     'Colonoscopy with polypectomy upon withdrawal.',
                     'Colonoscopy with biopsies taken when abnormal mucosa was seen.',
                     'Colonoscopy with removal of a polyp that had a stalk.', 'Colonoscopy was uncomplicated.',
                     'Colonoscopy (diagnostic) to the terminal ileum.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, 'Colonoscopy')
                self.assertEqual(status, 'performed', cues)
        for line in ('EGD with duodenal biopsies to evaluate for possible celiac disease.',
                     'EUS-guided fine-needle biopsy of a mass that was suspicious for malignancy.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(read(text, line.split()[0].split('-')[0])[0], 'performed')

    def test_findings_text_about_another_act_does_not_hold_the_service(self):
        for line in ('Colonoscopy showed a large polyp in the ascending colon that will require EMR at a later date.',
                     'Colonoscopy revealed a 3 cm polyp, which is to be removed at a later date.',
                     'Colonoscopy showed a 3 cm polyp in the ascending colon, for EMR at a later date.',
                     'Colonoscopy with polypectomy of a polyp that had been seen previously on CT.',
                     'Colonoscopy with cold snare polypectomy, but the patient may need surveillance later.'):
            text = HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_round1_rules_kept(self):
        """Outside a procedure heading only an extent continues after 'to'; a future after 'to' never does."""
        for line in ('Findings: Colonoscopy to check for recurrence.', 'Findings: Colonoscopy to evaluate the polyp.',
                     'Procedure: Colonoscopy to be scheduled.', 'Procedure: Colonoscopy to follow.',
                     'Procedure: Colonoscopy to come.', 'Procedure: Colonoscopy to check for recurrence.'):
            with self.subTest(line=line):
                self.assertNotEqual(read(HEADER + line + '\n', 'Colonoscopy')[0], 'performed')


class Status6QualifierAnywhereInTheClauseTests(unittest.TestCase):
    """status:6 - a planned, historical, pending or questioned qualifier anywhere after the name in its
    clause, or a refusal before it, keeps the section from speaking for the service."""

    EUS_LINES = ('EUS with fine-needle biopsy at a later date.', 'EUS with fine-needle biopsy once the INR is corrected.',
                 'EUS with fine-needle biopsy at an outside hospital last year.',
                 'EUS with fine-needle biopsy (to confirm with the patient).',
                 'The patient opted out of EUS with fine-needle biopsy.',
                 'The patient left before the EUS with fine-needle biopsy.')

    def test_the_claimed_eus_lines(self):
        for line in self.EUS_LINES:
            text = HEADER + 'Indication: A 2.4 cm pancreatic head mass on CT.\nProcedure: ' + line + '\n'
            with self.subTest(line=line):
                self.assertNotIn(family(text, 'gi.eus'), POSITIVE)
                self.assertNotEqual(fact_value(text, 'gi.eus', 'tissue_sampling'), 'FNB')
                proposals, _ = run_engine(text, [('43242', 'EUS with fine-needle biopsy')])
                self.assertNotEqual(proposals['43242'].status, 'ready')

    def test_a_refusal_before_the_name_is_about_today(self):
        for line in ('The patient opted out of EUS with fine-needle biopsy.',
                     'The patient left before the EUS with fine-needle biopsy.',
                     'The patient chose to forgo EUS.', 'The patient elected not to undergo EUS.',
                     'The patient decided against EUS.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.eus'), 'negated')
        # the refusal denies the section-read service line above it: it is not about earlier encounters
        text = HEADER + 'Procedure: EUS\nThe patient left before the EUS could be started.\n'
        self.assertEqual(family(text, 'gi.eus'), 'negated')

    def test_the_colonoscopy_matrix(self):
        for heading in ('Procedure:', 'Findings:', 'Technique:'):
            for line in ('Colonoscopy with polypectomy pending clearance.', 'Colonoscopy with polypectomy, date TBD.',
                         'Colonoscopy with polypectomy to be determined.', 'Colonoscopy with polypectomy last year.',
                         'Colonoscopy with polypectomy elsewhere.', 'Colonoscopy with polypectomy previously.',
                         'Colonoscopy with polypectomy: unknown.', 'The patient chose to forgo colonoscopy.',
                         'Colonoscopy with polypectomy at an outside hospital.',
                         'Colonoscopy with polypectomy when the INR is corrected.',
                         'Colonoscopy with polypectomy, requested by the referring physician.'):
                text = HEADER + heading + ' ' + line + '\n'
                with self.subTest(heading=heading, line=line):
                    self.assertNotIn(family(text, 'gi.colonoscopy'), POSITIVE)
                    status, cues = read(text, 'olonoscopy')
                    self.assertNotEqual(status, 'performed', cues)
                    self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)

    def test_controls_stay_performed(self):
        for line in ('EUS with fine-needle biopsy of the pancreatic head mass.', 'Colonoscopy with polypectomy.',
                     'Colonoscopy with cold snare polypectomy of a 6 mm sigmoid polyp that was retrieved.',
                     'The patient underwent colonoscopy with polypectomy.',
                     'Under monitored anesthesia care, colonoscopy with polypectomy.',
                     'Colonoscopy with polypectomy, which was uncomplicated.',
                     'Colonoscopy with polypectomy of the last remaining polyp.'):
            slug = 'gi.eus' if 'EUS' in line else 'gi.colonoscopy'
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(family(text, slug), 'performed')


STATUS9 = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the splenic flexure, where an '
           'obstructing mass was biopsied. On her colonoscopy in 2023 the cecum was reached.\n')


class Status9FactsFromAnotherProcedureTests(unittest.TestCase):
    """status:9 - a fact in a clause about a procedure not done at this encounter never supplies
    today's facts."""

    @staticmethod
    def colon(body):
        return HEADER + 'Procedure: Colonoscopy\nFindings: ' + body + '\n'

    def test_the_claimed_input_is_incomplete(self):
        self.assertEqual(fact_value(STATUS9, 'gi.colonoscopy', 'extent'), 'incomplete: splenic flexure')
        self.assertEqual(family(STATUS9, 'gi.colonoscopy'), 'incomplete')
        proposals, _ = run_engine(STATUS9, [('45380', 'where an obstructing mass was biopsied')])
        item = proposals['45380']
        self.assertIsNotNone(check(item, 'service.incomplete'))
        self.assertTrue(item.modifier_considerations)
        self.assertNotIn('cecum', item.rationale)

    def test_undated_history_and_other_facts(self):
        for sentence in ('Her prior colonoscopy reached the cecum.', 'On her colonoscopy in 2023 the cecum was reached.',
                         'During the previous colonoscopy the scope was advanced to the cecum.'):
            text = self.colon('The colonoscope was advanced to the splenic flexure. ' + sentence)
            with self.subTest(sentence=sentence):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'incomplete: splenic flexure')
        text = self.colon('The colonoscope was advanced to the cecum. On her colonoscopy in 2023 a polyp was removed '
                          'with a cold snare.')
        self.assertNotIn('cold snare', fact_value(text, 'gi.colonoscopy', 'interventions') or '')
        text = (HEADER + 'Procedure: ERCP\nFindings: The duodenoscope was advanced to the papilla. Deep biliary '
                'cannulation was achieved. On her ERCP in 2021 the cannulation failed.\n')
        self.assertEqual(fact_value(text, 'gi.ercp', 'cannulation'), 'successful')
        text = (HEADER + 'Procedure: EUS\nFindings: The echoendoscope was advanced to the duodenum. A 2 cm pancreatic '
                'cyst was seen. On her EUS in 2023 the cyst underwent FNA.\n')
        self.assertNotIn('FNA', fact_value(text, 'gi.eus', 'tissue_sampling') or '')
        text = (HEADER + 'Procedure: Flexible sigmoidoscopy\nFindings: The sigmoidoscope was advanced to 30 cm. Her '
                'flexible sigmoidoscopy in 2022 was advanced to 50 cm.\n')
        self.assertEqual(fact_value(text, 'gi.flex_sig', 'extent'), '30 cm')
        text = self.colon('The colonoscope was advanced to the cecum. One polyp was removed with a cold snare. On her '
                          'colonoscopy in 2023 the endoscopist found two polyps.')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'polyp_count'), '1')

    def test_controls_keep_todays_facts(self):
        for body in ('The colonoscope was advanced to the cecum; her prior colonoscopy in 2023 was normal.',
                     'Compared with her 2023 colonoscopy, the cecum was reached today.',
                     'Compared with her 2023 colonoscopy, the cecum was reached.',
                     'The cecum was reached, as on her prior colonoscopy.',
                     'The cecum was reached today despite her prior incomplete colonoscopy.',
                     'The cecum was reached in this patient with no prior colonoscopy.'):
            with self.subTest(body=body):
                self.assertEqual(fact_value(self.colon(body), 'gi.colonoscopy', 'extent'), 'cecum')
        text = self.colon('The colonoscope was advanced to the cecum. Two polyps were removed with a cold snare.')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'interventions'), 'cold snare')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'polyp_count'), '2')


if __name__ == '__main__':
    unittest.main()
