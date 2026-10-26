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
from studio.gi.profiles import DETECTED_FAMILIES
from studio.gi.sections import layout
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, RoutingResult, from_jsonable,
                          to_jsonable)
from studio.validation import engine as validation_engine
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


class Status5CancelledNextLineTests(unittest.TestCase):
    """status:5 - a status line, a non-referring next sentence or a later clause that cancels or
    denies the service named before it keeps the section from making it performed."""

    LINE = 'EUS with fine-needle biopsy of the pancreatic head mass.'

    def note(self, nxt):
        return HEADER + f'Procedure: {self.LINE}\n{nxt}\nIndication: A 2.4 cm pancreatic head mass on CT.\n'

    def test_the_claimed_next_lines(self):
        for nxt in ('Status: Cancelled.', 'Procedure status: Not performed - the patient had eaten breakfast.',
                    'However, it was not performed because the patient had eaten breakfast.',
                    'Unfortunately, the patient declined after consent.', 'Status: Not performed.', 'Not performed.',
                    'Cancelled.', 'Patient declined.', 'Pt refused.', 'Status: Postponed.', 'Status: Declined by patient.',
                    'Ultimately it was not done.', 'Status: Pending.', 'Status: TBD'):
            text = self.note(nxt)
            with self.subTest(nxt=nxt):
                self.assertNotIn(family(text, 'gi.eus'), POSITIVE)
                self.assertNotEqual(fact_value(text, 'gi.eus', 'tissue_sampling'), 'FNB')
                proposals, _ = run_engine(text, [('43242', self.LINE)])
                self.assertNotEqual(proposals['43242'].status, 'ready')
                status, cues = read(text, self.LINE)
                self.assertNotEqual(status, 'performed', cues)
                self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)

    def test_the_same_for_other_services_and_headings(self):
        for heading in ('Procedure:', 'Procedures performed:'):
            for lines, slug in (('Colonoscopy with biopsy.\nStatus: Cancelled.', 'gi.colonoscopy'),
                                ('Colonoscopy with biopsy.\nProcedure status: Not performed.', 'gi.colonoscopy'),
                                ('Colonoscopy with biopsy.\nHowever, it was not performed.', 'gi.colonoscopy'),
                                ('EGD with biopsy of the antrum.\nNot performed.', 'gi.egd'),
                                ('EGD with biopsy of the antrum.\nCancelled.', 'gi.egd'),
                                ('EGD with biopsy of the antrum.\nPatient declined.', 'gi.egd'),
                                ('EUS\nProcedure status: Not performed - the patient had eaten breakfast.', 'gi.eus'),
                                ('EUS\nHowever, it was not performed because the patient had eaten breakfast.', 'gi.eus')):
                text = HEADER + heading + ' ' + lines + '\n'
                with self.subTest(heading=heading, lines=lines):
                    self.assertNotIn(family(text, slug), POSITIVE)

    def test_a_later_clause_of_the_same_sentence(self):
        for line, slug in (('Colonoscopy with biopsy; not performed.', 'gi.colonoscopy'),
                           ('Colonoscopy with biopsy, but it was not performed.', 'gi.colonoscopy'),
                           ('Colonoscopy with polypectomy; cancelled.', 'gi.colonoscopy'),
                           ('EGD with dilation; patient declined.', 'gi.egd')):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                self.assertNotIn(family(text, slug), POSITIVE)

    def test_ordinary_next_lines_keep_the_service_performed(self):
        for nxt in ('No complications.', 'No polyps were found.', 'No bleeding.', 'It was not difficult.',
                    'Not difficult.', 'Status: Completed.', 'Status: stable.', 'The patient tolerated the procedure well '
                    'without complications.', 'No sedation was given.', 'Patient declined sedation.',
                    'However, it was uneventful.', 'No immediate complications.',
                    'No retroflexion was performed in the rectum.', 'Repeat in 3 years.', 'Patient not sedated.',
                    'No prep issues.', 'Status: Completed after the patient initially declined.'):
            text = HEADER + f'Procedure: {self.LINE}\n{nxt}\n'
            with self.subTest(nxt=nxt):
                self.assertEqual(family(text, 'gi.eus'), 'performed')
        for line in ('Colonoscopy with polypectomy; no complications.', 'Colonoscopy with polypectomy, but the patient '
                     'declined sedation.', 'Colonoscopy with polypectomy; however, biopsies were not taken.'):
            with self.subTest(line=line):
                self.assertEqual(family(HEADER + 'Procedure: ' + line + '\n', 'gi.colonoscopy'), 'performed')
        text = HEADER + 'Procedure: Colonoscopy with polypectomy; EGD cancelled.\n'  # the later clause is the EGD's
        self.assertEqual((family(text, 'gi.colonoscopy'), family(text, 'gi.egd')), ('performed', 'cancelled'))

    def test_an_abort_after_the_start_stays_incomplete(self):
        text = HEADER + 'Procedure: Colonoscopy with biopsy.\nAborted at 30 cm.\n'
        self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')
        status, cues = read(text, 'Colonoscopy with biopsy.')
        self.assertEqual(status, 'incomplete', cues)  # the started procedure is kept, not held as cancelled

    def test_status0_bare_line_beside_a_denied_other_act(self):
        text = colon_with_plan('Colonoscopy\nPatient not sedated.')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertTrue(ready(run_engine(text, [('45385', POLYPS)])[0]['45385']))


EMR_LINE = 'Colonoscopy with EMR of the ascending colon polyp at a tertiary center.'


def emr_note(heading):
    return (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 30 mm laterally '
            'spreading polyp in the ascending colon was tattooed and not removed.\n' + heading + '\n' + EMR_LINE + '\n')


class Status7ColonlessHeadingTests(unittest.TestCase):
    """status:7 - an unknown heading without a colon no longer continues the previous positive section
    when its words name a plan or a history; a findings sub-label or a title stays content."""

    def assert_planned_emr_excluded(self, text, kind):
        self.assertEqual(layout(text).section_at(text.index(EMR_LINE)).kind, kind)
        self.assertNotIn('EMR', fact_value(text, 'gi.colonoscopy', 'interventions') or '')
        proposals, _ = run_engine(text, [('45390', EMR_LINE)])
        self.assertEqual(proposals['45390'].bucket, 'excluded', proposals['45390'].status)

    def test_the_claimed_headings(self):
        for heading in ('Further management', 'Planned procedures', 'Future plan', 'Further management:'):
            with self.subTest(heading=heading):
                self.assert_planned_emr_excluded(emr_note(heading), 'plan')
        for heading in ('Further management:', 'Planned procedures:', 'Future plan:'):  # with the line inline
            text = emr_note(heading).replace(heading + '\n', heading + ' ')
            with self.subTest(inline=heading):
                self.assert_planned_emr_excluded(text, 'plan')

    def test_unknown_plan_and_history_labels_without_a_colon(self):
        for heading, kind in (('Upcoming procedures', 'plan'), ('Recommended interventions', 'plan'),
                              ('Endoscopic management', 'plan'), ('Further evaluation', 'plan'),
                              ('Summary and recommendations', 'plan'), ('Next appointments', 'plan'),
                              ('Earlier endoscopic work-up', 'history'), ('Previous endoscopic studies', 'history')):
            with self.subTest(heading=heading):
                self.assert_planned_emr_excluded(emr_note(heading), kind)

    def test_round1_case_a_with_the_colon_removed(self):
        for heading in ('Summary and recommendations', 'Planned procedures', 'Next appointments'):
            text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. The colon was '
                    'normal.\n' + heading + '\nEUS for evaluation of the pancreatic cyst seen on CT.\n')
            with self.subTest(heading=heading):
                self.assertNotIn(family(text, 'gi.eus'), POSITIVE)
                self.assertIsNone(fact_value(text, 'gi.eus', 'target'))

    def test_a_word_heading_paragraph(self):
        import io

        import docx
        from studio.ingest import Limits
        from studio.ingest import docx as docx_ingest
        document = docx.Document()
        document.add_paragraph('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT')
        document.add_paragraph('Date of service: 2026-10-21')
        document.add_paragraph('Procedure: Colonoscopy')
        document.add_paragraph('Findings: The colonoscope was advanced to the cecum. A 30 mm laterally spreading polyp in '
                               'the ascending colon was tattooed and not removed.')
        document.add_heading('Upcoming procedures', level=2)
        document.add_paragraph(EMR_LINE)
        buffer = io.BytesIO()
        document.save(buffer)
        result = docx_ingest.extract_docx(buffer.getvalue(), Limits())
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertIn('\nUpcoming procedures\n', result.text)
        self.assert_planned_emr_excluded(result.text, 'plan')

    def test_findings_sub_labels_and_titles_stay_content(self):
        for heading in ('Previous anastomosis', 'Prior polypectomy site', 'Sigmoid colon', 'Old blood',
                        'Previous stent procedures'):
            text = emr_note(heading)
            with self.subTest(heading=heading):
                self.assertEqual(layout(text).section_at(text.index(EMR_LINE)).kind, 'findings')
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nOffice follow-up visit - progress note\nDate of service: '
                '2026-10-21\nPlace of service: Office\nPatient status: Established patient.\nChief complaint\nReflux.\n')
        self.assertEqual(layout(text).section_at(text.index('Place of service')).kind, 'other')
        self.assertEqual(extract_context(text)['setting'].value, 'office')


DISCUSSED = ('SYNTHETIC TEST NOTE - NOT A REAL PATIENT\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\n'
             'Established patient office visit.\nChief complaint: Change in bowel habits.\n{section}\n'
             'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
VISIT = [('99214', 'Established patient office visit.')]
NEW_ENGINE = validation_engine.ENGINE_VERSION != 'cpt-studio-validation@2'


class DiscussionHeadingTests(unittest.TestCase):
    """Coordination with the validation repair: discussion, counseling and education sections never
    document a procedure done at this encounter, so they are plan sections; a procedure performed in a
    Procedure section still holds the visit."""

    SECTIONS = ('Discussion: Colonoscopy was discussed; the patient will consider it.',
                'Counseling: Risks and benefits of colonoscopy were reviewed.',
                'Patient education: Colonoscopy preparation was explained.',
                'Risks and benefits: Colonoscopy, including perforation and bleeding.',
                'Recommendations discussed: Colonoscopy in 3 months.')

    def test_the_headings_open_plan_sections(self):
        for section in self.SECTIONS:
            text = DISCUSSED.format(section=section)
            with self.subTest(section=section):
                mention = routed(text).finding('gi.colonoscopy').mentions[0]
                self.assertEqual(mention.section, 'plan')
                self.assertNotIn(mention.status, POSITIVE)
                self.assertFalse(any(cue.startswith('performed:') for cue in mention.cues), mention.cues)
                self.assertNotIn(family(text, 'gi.colonoscopy'), POSITIVE)

    def test_a_discussed_procedure_read_as_planned_does_not_hold_the_visit(self):
        for section in self.SECTIONS[1:]:
            text = DISCUSSED.format(section=section)
            with self.subTest(section=section):
                self.assertTrue(ready(run_engine(text, VISIT)[0]['99214']))

    @unittest.skipUnless(NEW_ENGINE, 'a hedged plan-section mention releases the visit from cpt-studio-validation@3 on')
    def test_a_hedged_discussed_procedure_does_not_hold_the_visit(self):
        self.assertTrue(ready(run_engine(DISCUSSED.format(section=self.SECTIONS[0]), VISIT)[0]['99214']))

    def test_a_performed_procedure_still_holds_the_visit(self):
        text = DISCUSSED.format(section='Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope '
                                        'was advanced to the cecum. A polyp was removed with a cold snare.')
        visit = run_engine(text, VISIT)[0]['99214']
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', clarified(visit))


FORM = '\n\n[PDF form fields on page 1]\nCold snare polypectomy: checked\nBiopsy: not checked'


def form_note(last):
    # The printed labels the form's fields name (round 3 contract:0): a field line that names no printed line holds
    # its page instead (tests/test_repairs_r3_forms_routing.py).
    return (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm polyp was '
            'seen.\nInterventions:\nBiopsy\nCold snare polypectomy\n' + last + FORM)


class Status10FormBlockTests(unittest.TestCase):
    """status:10 - the '[PDF form fields on page N]' block is a section of its own with no default: a
    checked box is never planned or historical, an unchecked one denies its item, whatever printed
    section precedes the block."""

    LASTS = ('Plan: Await pathology.', 'Recommendations: Await pathology.', 'Impression: Small polyp.',
             'Findings: Small polyp.')

    def test_the_block_reads_the_same_after_any_printed_section(self):
        readings = set()
        for last in self.LASTS:
            text = form_note(last)
            with self.subTest(last=last):
                checked, unchecked = read(text, 'Cold snare polypectomy: checked'), read(text, 'Biopsy: not checked')
                self.assertNotIn(checked[0], ('planned', 'historical'), checked)
                self.assertEqual(unchecked[0], 'negated', unchecked)
                proposals, _ = run_engine(text, [('45385', 'Cold snare polypectomy: checked')])
                self.assertTrue(ready(proposals['45385']), proposals['45385'].exclusion_reason)
                for phrase in ('Biopsy: not checked', 'Biopsy'):
                    excluded, _ = run_engine(text, [('45380', phrase)])
                    self.assertEqual(excluded['45380'].bucket, 'excluded', phrase)
                readings.add((checked, unchecked))
        self.assertEqual(len(readings), 1, readings)

    def test_each_field_line_is_its_own_sentence(self):
        """Field labels are often lower case; a field never runs on into the next one."""
        text = form_note('Impression: Small polyp.').replace(
            'Cold snare polypectomy: checked\nBiopsy: not checked', 'biopsy: not checked\ncold snare polypectomy: checked')
        status, cues = read(text, 'cold snare polypectomy: checked')
        self.assertEqual(status, 'uncertain')
        self.assertTrue(all(c.startswith(SILENT) for c in cues), cues)
        self.assertTrue(ready(run_engine(text, [('45385', 'cold snare polypectomy: checked')])[0]['45385']))
        # a cue in the next field ("scheduled") never reaches the field before it
        text = form_note('Impression: Small polyp.').replace(
            'Cold snare polypectomy: checked\nBiopsy: not checked',
            'procedure: colonoscopy with cold snare polypectomy\nfollow-up scheduled: 2026-12-01')
        status, cues = read(text, 'procedure: colonoscopy with cold snare polypectomy')
        # round 3 contract:10: a "procedure:" field reads as its printed line would, for itself alone
        self.assertNotIn(status, ('planned', 'historical'), cues)
        self.assertFalse(any('scheduled' in cue for cue in cues), cues)
        self.assertTrue(ready(run_engine(text, [('45385', 'procedure: colonoscopy with cold snare polypectomy')])[0]['45385']))

    def test_other_unchecked_values(self):
        for line in ('Biopsy: unchecked', 'Biopsy: no option selected', 'Biopsy: Not checked.'):
            text = form_note('Plan: Await pathology.').replace('Biopsy: not checked', line)
            with self.subTest(line=line):
                self.assertEqual(read(text, line)[0], 'negated')

    def test_block_lines_never_open_sections(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nEndoscopy unit - procedure form\nDate of service:\n'
                'Procedure performed:\nExtent reached:\n\n[PDF form fields on page 1]\ndos: 2026-10-21\n'
                'procedure: Colonoscopy, screening, to the cecum\nplan: Repeat colonoscopy in 3 years\n'
                'intervention: polyp removed with cold snare\nbiopsy: checked')
        kinds = {layout(text).section_at(text.index(phrase)).kind for phrase in
                 ('plan: Repeat', 'intervention:', 'biopsy: checked')}
        self.assertEqual(kinds, {'other'})
        # round 3 contract:10: a field labelled with a procedure heading reads as its printed line would, for that
        # line only; no field label governs another field
        self.assertEqual(layout(text).section_at(text.index('procedure: Colonoscopy')).kind, 'procedure')
        mention = routed(text).finding('gi.colonoscopy').mentions[0]
        self.assertEqual((mention.section, mention.status), ('procedure', 'performed'))
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'interventions'))

    def test_the_section_before_the_block_resumes_after_it(self):
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nPlan: Repeat'
                + FORM + '\n\ncolonoscopy with EMR in 3 months.\n')
        self.assertEqual(layout(text).section_at(text.index('colonoscopy with EMR')).kind, 'plan')
        self.assertEqual(read(text, 'colonoscopy with EMR')[0], 'planned')
        annotations = form_note('Plan: Await pathology.').replace('[PDF form fields', '[PDF annotation text')
        self.assertNotIn(read(annotations, 'Cold snare polypectomy: checked')[0], ('planned', 'historical'))


STATUS8 = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nIndication: Iron deficiency anemia. An EGD was '
           'performed last month at an outside hospital; the endoscope was advanced to the second part of the duodenum '
           'and the mucosa was normal.\nFindings: The colonoscope was advanced to the cecum. A 6 mm polyp in the sigmoid '
           'colon was removed with a cold snare.\n')
STATUS8_POLYP = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'


class Status8UndatedHistoryTests(unittest.TestCase):
    """status:8 - undated history (relative time, another provider or place) is never today's
    service, and an explicit performance in an indication section is held unless it says today."""

    def test_the_claimed_input(self):
        self.assertEqual(family(STATUS8, 'gi.egd'), 'historical')
        self.assertIsNone(fact_value(STATUS8, 'gi.egd', 'extent'))
        proposals, _ = run_engine(STATUS8, [('45385', STATUS8_POLYP),
                                            ('43235', 'An EGD was performed last month at an outside hospital')])
        self.assertTrue(ready(proposals['45385']))
        self.assertEqual(proposals['43235'].bucket, 'excluded')
        _, result = run_engine(STATUS8, [('45385', STATUS8_POLYP)])
        unproposed = next(c for c in result.encounter_checks if c.id == 'services.unproposed')
        self.assertNotIn('Upper GI endoscopy', unproposed.detail)

    def test_the_listed_wordings(self):
        for sentence in ('EGD was done last week at an outside hospital.', 'She underwent EGD last year.',
                         'EGD was performed earlier this month.', 'EGD was performed by her previous gastroenterologist.',
                         'She underwent an EGD at an outside facility in August.', 'An EGD was done elsewhere.',
                         'EGD was performed at another hospital.'):
            for lead in ('Indication: Anemia. ', 'Comments: Anemia. ', 'Findings: '):
                text = (HEADER + 'Procedure: Colonoscopy\n' + lead + sentence + '\nFindings: The colonoscope was '
                        'advanced to the cecum.\n')
                with self.subTest(lead=lead, sentence=sentence):
                    self.assertEqual(family(text, 'gi.egd'), 'historical')
                    self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_an_unlisted_wording_in_an_indication_is_held(self):
        text = (HEADER + 'Procedure: Colonoscopy\nIndication: Anemia. An EGD was performed in August; the endoscope was '
                'advanced to the duodenum.\nFindings: The colonoscope was advanced to the cecum.\n')
        self.assertNotIn(family(text, 'gi.egd'), POSITIVE)
        self.assertIsNone(fact_value(text, 'gi.egd', 'extent'))
        proposals, _ = run_engine(text, [('43235', 'An EGD was performed in August')])
        self.assertNotEqual(proposals['43235'].status, 'ready')

    def test_controls_stay_performed(self):
        for text, slug in (
                (HEADER + 'Procedure: EGD performed today.\nFindings: The gastroscope was advanced to the duodenum.\n', 'gi.egd'),
                (HEADER + 'Indication: Dysphagia. EGD was performed today for food impaction.\n', 'gi.egd'),
                (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Bleeding over the '
                          'past week was from a polyp, which was removed with a cold snare.\n', 'gi.colonoscopy'),
                (HEADER + 'Procedure: Colonoscopy for rectal bleeding since last month.\n', 'gi.colonoscopy'),
                (HEADER + 'Procedure: Colonoscopy for bleeding that started two weeks ago.\n', 'gi.colonoscopy'),
                (HEADER + 'Procedure: Colonoscopy for anemia noted over the last year.\n', 'gi.colonoscopy')):
            with self.subTest(text=text):
                self.assertEqual(family(text, slug), 'performed')
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A polyp was removed '
                'with a cold snare.\n')
        self.assertTrue(ready(run_engine(text, [('45385', 'A polyp was removed with a cold snare.')])[0]['45385']))
        self.assertEqual(family(HEADER + 'Colonoscopy five years ago was normal.\n', 'gi.colonoscopy'), 'historical')

    def test_a_request_is_not_history(self):
        """Coordination (orchestrator probe): "by the referring physician" names who asked, not who did it."""
        text = (HEADER + 'Indication: Dysphagia. Pancreatic cyst on CT; EUS requested by the referring physician.\n'
                'Procedure: EGD\nFindings: The endoscope was advanced to the second part of the duodenum. Normal EGD.\n')
        status, cues = read(text, 'EUS')
        self.assertNotEqual(status, 'historical', cues)
        self.assertNotIn(family(text, 'gi.eus'), POSITIVE + ('historical',))
        for line in ('Indication: Pancreatic cyst; EUS requested by her previous gastroenterologist.',
                     'Indication: Pancreatic cyst; EUS was ordered by the outside physician.'):
            with self.subTest(line=line):
                self.assertNotEqual(family(HEADER + line + '\n', 'gi.eus'), 'historical')
        for line in ('Indication: Anemia. EGD was performed by her previous gastroenterologist.',
                     'Indication: Anemia. EGD was performed by the referring gastroenterologist.'):
            with self.subTest(line=line):
                self.assertEqual(family(HEADER + line + '\n', 'gi.egd'), 'historical')

    def test_an_office_visit_statement_in_an_indication_still_counts(self):
        text = (HEADER + 'Reason for visit: Established patient office visit was completed for reflux.\n'
                'Medical decision making: low.\n')
        self.assertEqual(family(text, 'gi.office_em'), 'performed')
        visit = next(m for m in routed(text).finding('gi.office_em').mentions if m.span.text == 'office visit')
        self.assertEqual(visit.status, 'performed', visit.cues)


class AsScheduledTests(unittest.TestCase):
    """Coordination (orchestrator probe, pre-existing): "as scheduled" and its kin describe the booking a done
    service kept, never a future; "is scheduled", "scheduled for <date>", "will be" and "to be scheduled" stay
    planned."""

    BANDING = ('SYNTHETIC TEST NOTE - NOT A REAL PATIENT\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\n'
               'Established patient.\nChief complaint: Rectal bleeding.\nAssessment and plan:\nGrade II internal '
               'hemorrhoids.\nRubber band ligation of an internal hemorrhoid was performed today as scheduled.\n'
               'Medical decision making: low.\nTotal time on the date of the encounter was 24 minutes.\n')

    def test_a_kept_booking_reads_performed(self):
        for line in ('Colonoscopy was performed today as scheduled.', 'Colonoscopy was performed today as planned.',
                     'Colonoscopy was performed as previously scheduled.', 'Colonoscopy was performed today as arranged.'):
            text = HEADER + 'Findings: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(read(text, line)[0], 'performed')
        for line in ('Procedure: Colonoscopy as scheduled.', 'Procedure: Colonoscopy as previously scheduled.'):
            self.assertEqual(read(HEADER + line + '\n', 'Colonoscopy')[0], 'performed', line)
        band = 'Rubber band ligation of an internal hemorrhoid was performed today as scheduled.'
        status, cues = read(self.BANDING, band)
        # round 4 routing:1 withdrew round 3b's release of this plan-section clause: it is held (uncertain, with
        # PLAN_TODAY), never performed and never planned (tests/test_repairs_r3_time.py Routing26PlanSectionTodayTests)
        self.assertEqual(status, 'uncertain', cues)
        self.assertIn('performed: was performed', cues)
        self.assertIn(detect.PLAN_TODAY, cues)
        proposals, _ = run_engine(self.BANDING, [('46221', band)])
        self.assertEqual(proposals['46221'].bucket, 'selected', proposals['46221'].exclusion_reason)

    def test_a_future_booking_stays_planned(self):
        for line in ('Colonoscopy is scheduled for 2026-11-03.', 'Colonoscopy is scheduled.', 'Colonoscopy will be scheduled.',
                     'Colonoscopy to be scheduled.', 'Colonoscopy has been arranged.'):
            text = HEADER + 'Findings: ' + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(read(text, line)[0], 'planned')


class Status12DeniedFindingBesideAnActTests(unittest.TestCase):
    """status:12 - a cited sentence that states the act and denies a finding reads performed; a
    denied finding quoted alone is still held."""

    def test_the_claimed_input_and_variants(self):
        for procedure, sentence, code in (
                ('Colonoscopy', 'The colonoscope was advanced to the cecum and no polyps were seen.', '45378'),
                ('Colonoscopy', 'The colonoscope was advanced to the terminal ileum without looping.', '45378'),
                ('Colonoscopy', 'The scope was advanced to the cecum; no masses or polyps were identified.', '45378'),
                ('Colonoscopy', 'The colonoscope was advanced to the cecum without difficulty and no polyps were seen.',
                 '45378'),
                ('Colonoscopy', 'The colonoscope was inserted into the rectum and advanced to the cecum; no lesions were '
                                'found.', '45378'),
                ('EGD', 'The endoscope was advanced to the second part of the duodenum and no ulcers were seen.', '43235')):
            text = HEADER + f'Procedure: {procedure}\nFindings: {sentence}\n'
            with self.subTest(sentence=sentence):
                status, cues = read(text, sentence)
                self.assertEqual(status, 'performed', cues)
                self.assertTrue(ready(run_engine(text, [(code, sentence)])[0][code]))

    def test_a_denied_finding_alone_is_still_held(self):
        text = HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. No polyps were seen.\n'
        self.assertEqual(read(text, 'No polyps were seen.')[0], 'uncertain')
        proposals, _ = run_engine(text, [('45385', 'No polyps were seen.')])
        self.assertEqual(proposals['45385'].status, 'needs_clarification')
        # a performance word inside the denied finding itself states no act
        text = HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. No polyps were visualized.\n'
        self.assertEqual(read(text, 'No polyps were visualized.')[0], 'uncertain')
        text = HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced; no polyps were removed.\n'
        self.assertEqual(read(text, 'no polyps were removed.')[0], 'negated')


class Status16LineWrapTests(unittest.TestCase):
    """status:16 - a layout line break after a word a sentence cannot end on never splits a negation
    from the service named on the next line."""

    CLAIM = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp '
             'was removed with a\ncold snare. The patient asked about the pancreatic cyst; because of time constraints, '
             'no\nEUS of the pancreatic cyst was performed today.\n')

    def test_the_claimed_pdf_text(self):
        self.assertEqual(family(self.CLAIM, 'gi.eus'), 'negated')
        proposals, _ = run_engine(self.CLAIM, [('43259', 'EUS of the pancreatic cyst was performed today.')])
        self.assertNotEqual(proposals['43259'].status, 'ready')
        self.assertEqual(family(self.CLAIM, 'gi.colonoscopy'), 'performed')

    def test_the_variants(self):
        for body, slug in (('Findings: The cecum was reached. No\nEGD was done.', 'gi.egd'),
                           ('Findings: The cecum was reached.\nThe mucosa was normal. No\nEGD was done.', 'gi.egd'),
                           ('Findings: The cecum was reached.\nThe patient declined the\nEGD.', 'gi.egd'),
                           ('Findings: The papilla was not seen, so no\nERCP was performed during this session.', 'gi.ercp'),
                           ('Findings: The examination was completed without\nEUS being performed.', 'gi.eus')):
            text = HEADER + 'Procedure: Colonoscopy\n' + body + '\n'
            with self.subTest(body=body):
                self.assertNotIn(family(text, slug), POSITIVE)

    def test_fields_lists_and_table_rows_never_run_on(self):
        for prev, nxt in (('Biopsy: no', 'EGD: performed'), ('Interventions | No', 'EGD | Performed'),
                          ('The polyp was removed, with no', '1. EGD was performed.'),
                          ('The patient was seen today. No', 'Date of service: 2026-10-21'), ('No', 'EGD was done.'),
                          ('The polyp was removed with the snare', 'EGD was performed.')):
            text = HEADER + 'Findings: The colonoscope was advanced to the cecum.\n' + prev + '\n' + nxt + '\n'
            with self.subTest(prev=prev, nxt=nxt):
                start = text.index(nxt)
                self.assertEqual(layout(text).sentence_for(start, start + 1)[0], start)
        text = HEADER + 'Procedure: EGD with biopsy.\nBiopsy: No\nEGD: performed\n'
        self.assertEqual(family(text, 'gi.egd'), 'performed')


class Status17IntentFromAQuestionTests(unittest.TestCase):
    """status:17 - intent is never read from a question or a hedge; a stated intent still is."""

    @staticmethod
    def note(indication):
        return (HEADER + f'Indication: {indication}\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to the '
                'cecum. The colon was normal.\n')

    def test_questioned_intents(self):
        for indication in ('Is this a screening colonoscopy? The patient reports intermittent hematochezia.',
                           'Screening colonoscopy?', '?screening.', 'Is this a surveillance colonoscopy?',
                           'Unclear whether this is a screening colonoscopy.'):
            with self.subTest(indication=indication):
                self.assertIsNone(fact_value(self.note(indication), 'gi.colonoscopy', 'intent'))
        proposals, _ = run_engine(self.note('Is this a screening colonoscopy? The patient reports intermittent '
                                            'hematochezia.'), [('45378', 'The colonoscope was advanced to the cecum.')])
        self.assertNotIn('screening', proposals['45378'].rationale)

    def test_stated_intents_are_kept(self):
        for indication, intent in (('Screening colonoscopy, average risk.', 'screening'),
                                   ('Screening colonoscopy, average risk. Is the patient on anticoagulation?', 'screening'),
                                   ('Surveillance colonoscopy; prior colonoscopy in 2019 showed adenomas.', 'surveillance'),
                                   ('Diagnostic colonoscopy for hematochezia.', 'diagnostic')):
            with self.subTest(indication=indication):
                self.assertEqual(fact_value(self.note(indication), 'gi.colonoscopy', 'intent'), intent)


SEPARATE_BASE = ('SYNTHETIC TEST NOTE - NOT A REAL PATIENT\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\n'
                 'Established patient office visit for rectal bleeding.\nProcedure: Flexible sigmoidoscopy with biopsy.\n'
                 'Findings: The sigmoidoscope was advanced to 40 cm. A biopsy was taken from the rectum.\n'
                 'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
SEPARATE_PICKS = [('99214', 'Established patient office visit for rectal bleeding.'),
                  ('45331', 'A biopsy was taken from the rectum.')]


def separate_em(text):
    return next((f for f in routed(text).finding('gi.office_em').facts if f.name == 'separate_em'), None)


class Status14SeparateEmStatementTests(unittest.TestCase):
    """status:14 - a requirement, a condition or a statement about another encounter is not the
    separately identifiable E/M statement; the visit stays held."""

    def test_the_claimed_and_listed_statements(self):
        for extra in ('Billing note: modifier 25 requires that a significant, separately identifiable E/M service is '
                      'documented.',
                      'A significant, separately identifiable E/M service was provided at the previous visit.',
                      'Modifier 25 applies only when a significant, separately identifiable E/M service is documented.',
                      'Modifier 25 applies when a significant, separately identifiable E/M service is documented.',
                      'Modifier 25 is appended once a significant, separately identifiable E/M service is documented.',
                      'On 2026-09-15 a significant, separately identifiable E/M service was provided.',
                      'At the last visit a significant, separately identifiable E/M service was provided.',
                      'A significant, separately identifiable E/M service was provided at the prior consultation.',
                      '\nADDENDUM (revision 2, added 2026-10-22 09:00 UTC)\nThe significant, separately identifiable E/M '
                      'service was provided at the 2026-10-14 consultation. Today was the usual pre-procedure assessment.'):
            text = SEPARATE_BASE + extra + '\n'
            with self.subTest(extra=extra):
                self.assertIsNone(separate_em(text))
                proposals, _ = run_engine(text, SEPARATE_PICKS)
                self.assertEqual(proposals['99214'].status, 'needs_clarification')
                self.assertIn('separate_em', clarified(proposals['99214']))

    def test_statements_about_this_encounter_are_documented(self):
        for extra in ('A significant, separately identifiable E/M service was performed today.',
                      'On 2026-10-21 a significant, separately identifiable E/M service was provided.',
                      'Attestation: A significant, separately identifiable E/M service was performed.',
                      'A significant, separately identifiable E/M service was provided on the date of service.'):
            with self.subTest(extra=extra):
                fact = separate_em(SEPARATE_BASE + extra + '\n')
                self.assertIsNotNone(fact)
                self.assertEqual(fact.value, 'documented')

    def test_a_dated_statement_needs_the_date_of_service(self):
        undated_note = SEPARATE_BASE.replace('Date of service: 2026-10-21\n', '')
        self.assertIsNone(separate_em(undated_note + 'On 2026-10-21 a significant, separately identifiable E/M service was '
                                                     'provided.\n'))
        self.assertIsNotNone(separate_em(undated_note + 'A significant, separately identifiable E/M service was '
                                                        'provided.\n'))

    def test_the_evidence_quotes_the_rest_of_the_line(self):
        statement = 'A significant, separately identifiable E/M service was provided. Counseling took 20 minutes.'
        fact = separate_em(SEPARATE_BASE + statement + '\n')
        self.assertEqual(fact.evidence[0].text, statement)


SUB_ACT_NOTE = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to the '
                'cecum, identified by the appendiceal orifice and the ileocecal valve. {x}A 6 mm sigmoid polyp was removed '
                'with a cold snare.\n')


class Status15SubActTests(unittest.TestCase):
    """status:15 - a failed or aborted sub-act (terminal ileum intubation, ileocecal valve traversal,
    retroflexion) does not make a procedure that reached its expected extent incomplete."""

    FORMS = ('The terminal ileum was not intubated. ',
             'Terminal ileal intubation was aborted because of a stenotic ileocecal valve. ',
             'Retroflexion was attempted but aborted because of a narrow rectal vault. ',
             'The terminal ileum could not be intubated. ', 'Attempts to intubate the terminal ileum were unsuccessful. ',
             'The ileocecal valve could not be traversed. ',
             'The cecum was reached without intubation of the terminal ileum. ')

    def test_the_claimed_forms(self):
        for x in self.FORMS:
            text = SUB_ACT_NOTE.format(x=x)
            with self.subTest(x=x):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
                proposals, _ = run_engine(text, [('45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')])
                item = proposals['45385']
                self.assertTrue(ready(item))
                self.assertIsNone(check(item, 'service.incomplete'))
                self.assertFalse(item.modifier_considerations)

    def test_an_egd_retroflexion(self):
        text = (HEADER + 'Procedure: EGD\nFindings: The gastroscope was advanced to the second part of the duodenum. '
                'Retroflexion was aborted because of patient discomfort. Biopsies were taken from the antrum.\n')
        self.assertEqual(family(text, 'gi.egd'), 'performed')

    def test_the_procedure_short_of_its_extent_stays_incomplete(self):
        for body in ('The colonoscope could not be advanced beyond the splenic flexure, so the terminal ileum was not '
                     'intubated.', 'The colonoscope was advanced to the splenic flexure. The procedure was aborted at the '
                     'splenic flexure.', 'The colonoscope was advanced to the transverse colon. The cecum and terminal '
                     'ileum could not be reached.', 'The terminal ileum could not be intubated.',
                     'The colonoscope was advanced to the cecum. The terminal ileum and the sigmoid colon were not '
                     'visualized.'):
            text = HEADER + 'Procedure: Colonoscopy\nFindings: ' + body + '\n'
            with self.subTest(body=body):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')


class Status18ShorthandExtentTests(unittest.TestCase):
    """status:18 - shorthand extents ("to cecum", "to TI", "Extent: cecum", "to 30 cm", "to D2") are
    read; a denied or planned extent never is."""

    def test_the_claimed_inputs(self):
        for body, slug, code, evidence, extent in (
                ('Procedure: Colonoscopy to cecum with cold snare polypectomy.\nFindings: A 6 mm polyp was removed with a '
                 'cold snare. Biopsies were taken.', 'gi.colonoscopy', '45385', 'A 6 mm polyp was removed with a cold snare.',
                 'cecum'),
                ('Procedure: Colonoscopy to TI with cold snare polypectomy.\nFindings: A 6 mm polyp was removed with a '
                 'cold snare.', 'gi.colonoscopy', '45385', 'A 6 mm polyp was removed with a cold snare.', 'terminal ileum'),
                ('Procedure: Colonoscopy with cold snare polypectomy.\nExtent: cecum\nFindings: A 6 mm polyp was removed '
                 'with a cold snare.', 'gi.colonoscopy', '45385', 'A 6 mm polyp was removed with a cold snare.', 'cecum'),
                ('Procedure: Colonoscopy with cold snare polypectomy.\nExtent reached: terminal ileum\nFindings: A 6 mm '
                 'polyp was removed with a cold snare.', 'gi.colonoscopy', '45385',
                 'A 6 mm polyp was removed with a cold snare.', 'terminal ileum'),
                ('Procedure: Flexible sigmoidoscopy to 30 cm with biopsy.\nFindings: A biopsy was taken from the rectum.',
                 'gi.flex_sig', '45331', 'A biopsy was taken from the rectum.', '30 cm'),
                ('Procedure: EGD to D2 with biopsy.\nFindings: Biopsies were taken from the antrum.', 'gi.egd', '43239',
                 'Biopsies were taken from the antrum.', 'second part of duodenum')):
            text = HEADER + body + '\n'
            with self.subTest(body=body):
                self.assertEqual(fact_value(text, slug, 'extent'), extent)
                self.assertTrue(ready(run_engine(text, [(code, evidence)])[0][code]))

    def test_answers_and_other_shorthands(self):
        for body, slug, extent in (
                ('Procedure: Colonoscopy\nFindings: Furthest extent reached: cecum.', 'gi.colonoscopy', 'cecum'),
                ('Procedure: Colonoscopy\nFindings: The furthest extent reached was the cecum.', 'gi.colonoscopy', 'cecum'),
                ('Procedure: Colonoscopy to the terminal ileum.', 'gi.colonoscopy', 'terminal ileum'),
                ('Procedure: Diagnostic colonoscopy (TI) to the terminal ileum.', 'gi.colonoscopy', 'terminal ileum'),
                ('Procedure: Flexible sigmoidoscopy\nFindings: FS was performed to 35 cm.', 'gi.flex_sig', '35 cm'),
                ('Procedure: Flexible sigmoidoscopy\nFindings: Depth of insertion: 30 cm.', 'gi.flex_sig', '30 cm')):
            with self.subTest(body=body):
                self.assertEqual(fact_value(HEADER + body + '\n', slug, 'extent'), extent)

    def test_a_denied_or_planned_extent_is_not_read(self):
        for body in ('Procedure: Colonoscopy to the cecum was not possible.', 'Procedure: Colonoscopy to the cecum is planned.',
                     'Procedure: Colonoscopy\nFindings: Extent: cecum not reached.',
                     'Procedure: Colonoscopy\nPlan: Colonoscopy to the cecum next month.',
                     'Procedure: Colonoscopy\nFindings: No colonoscopy to the cecum was performed today.',
                     'Procedure: EGD\nFindings: Possible colonoscopy to the cecum.'):
            with self.subTest(body=body):
                self.assertNotEqual(fact_value(HEADER + body + '\n', 'gi.colonoscopy', 'extent'), 'cecum')
        text = HEADER + ('Procedure: Colonoscopy\nFindings: Extent reached: splenic flexure; the cecum could not be '
                         'reached.\n')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'incomplete: splenic flexure')


BOXED = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp '
         'was found.\nInterventions performed\n')


class Status11BoxAfterItsLabelTests(unittest.TestCase):
    """status:11 - a box after its label on the same line or table cell, or a '( )' box, is read; the
    layout of the item's own sentence decides which box governs; a yes/no pair is read by its options."""

    def assert_boxes(self, rows, biopsy, snare):
        text = BOXED + rows
        self.assertEqual(read(text, 'Biopsy')[0], biopsy, rows)
        self.assertEqual(read(text, 'Cold snare polypectomy')[0], snare, rows)
        interventions = fact_value(text, 'gi.colonoscopy', 'interventions') or ''
        self.assertEqual('biopsy' in interventions, biopsy == 'performed', (rows, interventions))
        self.assertEqual('cold snare' in interventions, snare == 'performed', (rows, interventions))
        proposals, _ = run_engine(text, [('45380', 'Biopsy')])
        self.assertEqual(proposals['45380'].bucket == 'excluded', biopsy == 'negated', rows)

    def test_the_claimed_layouts(self):
        for rows in ('Biopsy | ☐\nCold snare polypectomy | ☒\n', 'Biopsy: ☐\nCold snare polypectomy: ☒\n',
                     'Biopsy [ ]\nCold snare polypectomy [x]\n', '( ) Biopsy\n(x) Cold snare polypectomy\n',
                     'Biopsy | ☐ | Cold snare polypectomy | ☒\n', '☐ Biopsy ☒ Cold snare polypectomy\n'):
            with self.subTest(rows=rows):
                self.assert_boxes(rows, 'negated', 'performed')

    def test_a_checked_box_after_its_label_changes_nothing(self):
        self.assert_boxes('Biopsy | ☒\nCold snare polypectomy | ☒\n', 'performed', 'performed')
        self.assert_boxes('Biopsy [X]\nCold snare polypectomy (X)\n', 'performed', 'performed')

    def test_every_contract_glyph(self):
        for off in ('☐', '□', '◻', '◽', '❏', '❐', '❑', '❒', '[ ]', '[_]', '( )'):
            for on in ('☑', '☒', '✓', '✔', '■', '⌧', '[x]', '[X]', '(x)', '(X)'):
                with self.subTest(off=off, on=on):
                    text = BOXED + f'Biopsy: {off}\nCold snare polypectomy: {on}\n'
                    self.assertEqual(read(text, 'Biopsy')[0], 'negated')
                    self.assertEqual(read(text, 'Cold snare polypectomy')[0], 'performed')

    def test_yes_no_pairs_are_read_by_the_option_marked(self):
        for rows, biopsy, snare in (
                ('Biopsy taken: ☐ Yes ☒ No\nCold snare polypectomy: ☒ Yes ☐ No\n', 'negated', 'performed'),
                ('Biopsy taken: No ☐ Yes ☒\nCold snare polypectomy: No ☒ Yes ☐\n', 'performed', 'negated'),
                ('Biopsy taken: ☐ No ☒ Yes\nCold snare polypectomy: ☒ No ☐ Yes\n', 'performed', 'negated'),
                ('Biopsy taken: Yes ☐ No ☒\nCold snare polypectomy: Yes ☒ No ☐\n', 'negated', 'performed'),
                ('Biopsy: ☐ Yes\nCold snare polypectomy: ☒ Yes\n', 'negated', 'performed')):
            with self.subTest(rows=rows):
                self.assert_boxes(rows, biopsy, snare)

    def test_a_word_table_with_check_box_controls(self):
        from studio.ingest import Limits
        from studio.ingest import docx as docx_ingest
        from tests.support import docgen

        def control(checked):
            return ('<w:sdt><w:sdtPr><w14:checkbox><w14:checked w14:val="%d"/></w14:checkbox></w:sdtPr><w:sdtContent>'
                    '<w:r><w:t>%s</w:t></w:r></w:sdtContent></w:sdt>' % (checked, '☒' if checked else '☐'))

        def row(label, checked):
            return f'<w:tr><w:tc><w:p><w:r><w:t>{label}</w:t></w:r></w:p></w:tc><w:tc><w:p>{control(checked)}</w:p></w:tc></w:tr>'

        paragraphs = ''.join(f'<w:p><w:r><w:t>{line}</w:t></w:r></w:p>' for line in BOXED.strip('\n').split('\n'))
        body = paragraphs + '<w:tbl>' + row('Biopsy', 0) + row('Cold snare polypectomy', 1) + '</w:tbl>'
        result = docx_ingest.extract_docx(docgen.make_docx_from_body(body), Limits())
        self.assertEqual(result.status, 'ok', result.messages)
        self.assertTrue(result.text.endswith('Biopsy | ☐\nCold snare polypectomy | ☒'), result.text)
        self.assertEqual(read(result.text, 'Biopsy')[0], 'negated')
        self.assertEqual(fact_value(result.text, 'gi.colonoscopy', 'interventions'), 'cold snare')

    def test_the_box_of_another_sentence_or_item_never_governs(self):
        text = (HEADER + 'Procedure: Colonoscopy. Checklist: ☐ Biopsy. Findings: The colonoscope was advanced to the '
                'cecum. A polyp was removed with a cold snare.\n')
        self.assertEqual(read(text, 'Biopsy')[0], 'negated')
        self.assertEqual(read(text, 'Colonoscopy')[0], 'performed')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        text = HEADER + 'Procedure: Colonoscopy with biopsy \u2610\nFindings: The colonoscope was advanced to the cecum.\n'
        self.assertEqual((read(text, 'Colonoscopy')[0], read(text, 'biopsy')[0]), ('performed', 'negated'))
        text = HEADER + 'Findings: Checklist: \u2610 Biopsy. Colonoscopy with cold snare polypectomy was performed.\n'
        self.assertEqual((read(text, 'Biopsy')[0], read(text, 'Colonoscopy')[0]), ('negated', 'performed'))

    def test_a_no_option_label_is_not_an_unresolved_negation(self):
        text = BOXED + 'Cold snare polypectomy: ☒ Yes ☐ No\n'
        status, cues = read(text, 'Cold snare polypectomy')
        self.assertEqual(status, 'performed', cues)

    def test_the_reach_after_a_label_is_bounded(self):
        """Literal distances: a box 152 characters after its label governs it, one 252 after does not."""
        near = BOXED + 'Biopsy ' + 'x ' * 72 + '☐\n'
        far = BOXED + 'Biopsy ' + 'x ' * 122 + '☐\n'
        self.assertEqual(near.index('☐') - near.index('Biopsy'), 151)
        self.assertEqual(far.index('☐') - far.index('Biopsy'), 251)
        self.assertEqual(read(near, 'Biopsy')[0], 'negated')
        self.assertNotEqual(read(far, 'Biopsy')[0], 'negated')


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


OFFICE_NOTE = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\n'
               'Established patient office visit.\n{body}\nChief complaint: rectal bleeding.\n'
               'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
BOX_OFF, BOX_ON = '\N{BALLOT BOX}', '\N{BALLOT BOX WITH X}'


class Status19OtherProcedureTests(unittest.TestCase):
    """status:19 (medium, under-correction), routing part. An office note documenting a same-day procedure
    outside the detected families (hemorrhoid banding, anoscopy) routed only gi.office_em: nothing could hold
    the E/M, and the coverage checks reported every performed service as profiled. Routing now emits a
    gi.other finding (shared contract). A procedure's name, told by its form (_PROCEDURE_WORD), is read as the
    first sentence of a procedure section (and each item of its check-box lines), as the subject of an
    explicit performed clause, or as the object of "underwent" / "we performed"; never a detected family's
    own procedure, an examination, a test, "none", or a name led by a negation, a condition or a plan.
    Each mention is a procedure of its own, read alone by the ordinary status machinery."""

    CLAIM = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\n'
             'Established patient office visit.\nChief complaint: rectal bleeding.\n'
             'Procedure: Rubber band ligation of an internal hemorrhoid was performed today without complication.\n'
             'Medical decision making: moderate.\nTotal time: 32 minutes.\n')

    def office(self, body):
        return OFFICE_NOTE.format(body=body)

    def other(self, text):
        return routed(text).finding('gi.other')

    def test_the_claimed_banding_is_a_same_day_other_procedure(self):
        result = routed(self.CLAIM)
        other = result.finding('gi.other')
        self.assertEqual(other.status, 'performed')
        self.assertEqual([(m.family, m.span.text, m.status, m.section) for m in other.mentions],
                         [('gi.other', 'Rubber band ligation of an internal hemorrhoid', 'performed', 'procedure')])
        self.assertIn('performed: was performed', other.mentions[0].cues)
        self.assertEqual(other.mentions[0].sentence.text,
                         'Rubber band ligation of an internal hemorrhoid was performed today without complication.')
        self.assertEqual((other.facts, other.missing), ((), ()))
        self.assertEqual(result.finding('gi.office_em').status, 'performed')  # its MDM and time are documented
        self.assertEqual(result.document_kind, 'mixed')

    def test_the_coverage_check_no_longer_calls_every_performed_service_profiled(self):
        _, result = run_engine(self.CLAIM, [('99214', 'Established patient office visit.')])
        unsupported = next(c for c in result.encounter_checks if c.id == 'services.unsupported')
        self.assertNotEqual(unsupported.status, 'pass', unsupported.detail)

    def test_other_procedures_documented_as_done(self):
        for body, name in (('Anoscopy was performed today.', 'Anoscopy'),
                           ('After verbal consent, anoscopy was performed.', 'anoscopy'),
                           ('Anoscopy for rectal bleeding was performed.', 'Anoscopy for rectal bleeding'),
                           ('Rubber band ligation x3 completed today.', 'Rubber band ligation x3'),
                           ('The patient underwent rubber band ligation of two internal hemorrhoids.',
                            'rubber band ligation of two internal hemorrhoids'),
                           ('We performed an anoscopy.', 'anoscopy'),
                           ('After banding was performed, the patient was observed.', 'banding'),
                           ('Paracentesis was performed today; 3 L removed.', 'Paracentesis'),
                           ('Procedure: Anoscopy was performed.', 'Anoscopy'),
                           ('Anoscopy with banding of two internal hemorrhoids at the right anterior and right posterior '
                            'positions was performed without difficulty.', 'Anoscopy with banding of two internal '
                            'hemorrhoids at the right anterior and right posterior positions')):
            other = self.other(self.office(body))
            self.assertIsNotNone(other, body)
            self.assertEqual((other.status, [m.span.text for m in other.mentions]), ('performed', [name]), body)

    def test_its_status_comes_from_the_ordinary_readings(self):
        for body, status, mentions in (
                ('Procedure: Rubber band ligation scheduled for next week.', 'planned', [('Rubber band ligation', 'planned')]),
                ('Procedure: Anoscopy - patient declined.', 'negated', [('Anoscopy', 'negated')]),
                ('History: Hemorrhoidectomy was performed in 2015.', 'historical', [('Hemorrhoidectomy', 'historical')]),
                ('Anoscopy was performed at an outside facility.', 'historical', [('Anoscopy', 'historical')]),
                ('Anoscopy was performed last month.', 'historical', [('Anoscopy', 'historical')])):
            other = self.other(self.office(body))
            self.assertIsNotNone(other, body)
            self.assertEqual((other.status, [(m.span.text, m.status) for m in other.mentions]), (status, mentions), body)

    def test_an_office_procedure_heading_alone_is_held_as_for_every_family(self):
        body = 'Procedure: Anoscopy with banding of two internal hemorrhoids.'
        other = self.other(self.office(body))  # MDM and time documented: the heading alone does not establish it
        self.assertEqual(other.status, 'uncertain')
        self.assertEqual([m.span.text for m in other.mentions], ['Anoscopy with banding of two internal hemorrhoids'])
        self.assertIn(detect.HEADING_ONLY, other.mentions[0].cues)
        self.assertEqual(self.other(HEADER + 'Place of service: Office (POS 11)\n' + body + '\n').status, 'performed')

    def test_each_procedure_is_judged_alone(self):
        other = self.other(self.office('Procedure: Anoscopy - patient declined.\n'
                                       'Rubber band ligation x3 was performed today.'))
        self.assertEqual(other.status, 'performed')
        self.assertEqual([(m.span.text, m.status) for m in other.mentions],
                         [('Anoscopy', 'negated'), ('Rubber band ligation x3', 'performed')])
        # A denied anoscopy never makes the family read "negated" while a checked hemorrhoidectomy may be done.
        other = self.other(self.office(f'Procedure: {BOX_OFF} Anoscopy {BOX_ON} Hemorrhoidectomy'))
        self.assertEqual(other.status, 'uncertain')
        self.assertEqual([(m.span.text, m.status) for m in other.mentions],
                         [('Anoscopy', 'negated'), ('Hemorrhoidectomy', 'uncertain')])

    def test_each_item_of_a_check_box_line_names_its_procedure(self):
        for body, expected in (
                (f'Procedure: {BOX_ON} Anoscopy {BOX_OFF} Hemorrhoidectomy',
                 [('Anoscopy', 'uncertain'), ('Hemorrhoidectomy', 'negated')]),
                ('Procedure: Anoscopy [ ] Hemorrhoidectomy [x]', [('Anoscopy', 'negated'), ('Hemorrhoidectomy', 'uncertain')]),
                ('Procedure: Anoscopy [x] Hemorrhoidectomy [ ]', [('Anoscopy', 'uncertain'), ('Hemorrhoidectomy', 'negated')]),
                (f'Procedures:\n{BOX_OFF} Anoscopy\n{BOX_ON} Rubber band ligation\n{BOX_OFF} Hemorrhoidectomy',
                 [('Anoscopy', 'negated'), ('Rubber band ligation', 'uncertain'), ('Hemorrhoidectomy', 'negated')])):
            other = self.other(self.office(body))
            self.assertIsNotNone(other, body)
            self.assertEqual([(m.span.text, m.status) for m in other.mentions], expected, body)
        self.assertEqual(self.other(self.office(f'Procedures:\n{BOX_OFF} Anoscopy\n{BOX_OFF} Rubber band ligation')).status,
                         'negated')
        other = self.other(self.office(f'Procedure: {BOX_OFF} None {BOX_ON} Anoscopy'))  # "None" is no name
        self.assertEqual([(m.span.text, m.status) for m in other.mentions], [('Anoscopy', 'uncertain')])
        # A flattened two-column table ("Done | Not done"): the first box after an item governed it; an empty cell is
        # no name, and the items after it are still read. Round 4d BOXES3 (contract-r4d section 4, strict check-box
        # rows): an entry with two boxes cannot be paired in exactly one way (which column says done cannot be told
        # without the table's header), so each item is held, never negated by its first box.
        for body in (f'Procedure: Anoscopy | {BOX_ON} | {BOX_OFF} | Hemorrhoidectomy | {BOX_OFF} | {BOX_ON}',
                     f'Procedures:\nAnoscopy | {BOX_ON} | {BOX_OFF}\nHemorrhoidectomy | {BOX_OFF} | {BOX_ON}'):
            other = self.other(self.office(body))
            self.assertEqual([(m.span.text, m.status) for m in other.mentions],
                             [('Anoscopy', 'uncertain'), ('Hemorrhoidectomy', 'uncertain')], body)

    def test_a_long_subject_is_named_from_a_whole_word_within_reach(self):
        for body, name in (
                ('Because of persistent intermittent painless bright red blood per rectum over the past several months '
                 'despite fiber and sitz baths an anoscopy was performed.',
                 'painless bright red blood per rectum over the past several months despite fiber and sitz baths an '
                 'anoscopy'),  # the last OTHER_NAME_REACH characters before the participle, from a whole word
                ('Intermittent symptomatic uncomplicated nonthrombosed internal hemorrhoidal disease necessitating '
                 'outpatient rubber band ligation was performed.',
                 'symptomatic uncomplicated nonthrombosed internal hemorrhoidal disease necessitating outpatient rubber '
                 'band ligation')):
            text = self.office(body)
            other = self.other(text)
            self.assertIsNotNone(other, body)
            self.assertEqual([(m.span.text, m.status) for m in other.mentions], [(name, 'performed')], body)
            self.assertTrue(text[other.mentions[0].span.start - 1].isspace(), body)  # never the tail of a cut word

    def test_no_other_procedure_is_documented(self):
        for body in ('Anoscopy was not performed.', 'Anoscopy has not been performed.',
                     'No hemorrhoid banding was performed today.', 'She never underwent hemorrhoid banding.',
                     'Procedures: None performed today.', 'Procedure: None.', 'Labs were done today.',
                     'A rectal examination was performed.', 'Counseling was provided.',
                     'Procedure: The patient was placed in the left lateral position.',
                     'Procedure: Discussed risks and benefits.',
                     'Procedure: The risks and benefits of the procedure were explained.',
                     'Biopsy results were reviewed and treatment completed.',
                     'If banding were done today, she would need a follow-up visit.',
                     'Banding would be done if bleeding persists.', 'Banding to be done next week.',
                     'Banding can be done in the office.', 'Discussed hemorrhoid banding.',
                     'Procedure: Discussed hemorrhoid banding.', 'Procedure: Planned anoscopy.',
                     'Plan: Rubber band ligation of an internal hemorrhoid is scheduled for 2026-11-03.',
                     'Consultation for hemorrhoid banding was completed.', 'Evaluation for anoscopy was performed.'):
            self.assertIsNone(self.other(self.office(body)), body)

    def test_a_detected_familys_own_procedures_are_never_other(self):
        for text, slug in (
                (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Cold snare '
                 'polypectomy was performed. Biopsies were done. Tattoo injection was performed.\n', 'gi.colonoscopy'),
                (HEADER + 'Procedure: EUS\nFindings: The echoendoscope was advanced to the duodenum. Fine-needle biopsy '
                 'was performed.\n', 'gi.eus'),
                (HEADER + 'Procedure: EGD\nFindings: Esophageal dilation was performed with a balloon. The duodenum was '
                 'normal.\n', 'gi.egd'),
                (HEADER + 'Procedure: Colonoscopy\nTechnique: The procedure was performed under MAC. The risks and '
                 'benefits of the procedure were explained. The colonoscope was advanced to the cecum.\n',
                 'gi.colonoscopy'),
                (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Through the '
                 'colonoscope, rubber band ligation of internal hemorrhoids was performed.\n', 'gi.colonoscopy')):
            result = routed(text)
            self.assertEqual(result.finding(slug).status, 'performed', text)
            self.assertIsNone(result.finding('gi.other'), text)

    def test_the_verification_documents_name_no_other_procedure(self):
        for path in sorted(DOCS.glob('*.txt')):
            self.assertIsNone(routed(path.read_text(encoding='utf-8')).finding('gi.other'), path.name)

    def test_an_em_without_its_own_basis_is_held_beside_an_other_procedure_as_beside_any(self):
        result = routed(HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                                 'Anoscopy was performed today.\n')
        self.assertEqual(result.finding('gi.other').status, 'performed')
        em = result.finding('gi.office_em')
        self.assertEqual(em.status, 'uncertain')
        self.assertIn(detect.EM_WITHOUT_BASIS, em.mentions[0].cues)
        control = routed(HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n')
        self.assertEqual((control.finding('gi.office_em').status, control.finding('gi.other')), ('performed', None))

    def test_the_contract_shape(self):
        self.assertEqual(DETECTED_FAMILIES, ('gi.office_em', 'gi.egd', 'gi.colonoscopy', 'gi.flex_sig', 'gi.eus',
                                             'gi.ercp'))  # gi.other stays outside: its codes keep their own passage
        result = route(self.CLAIM, service_date(self.CLAIM))
        self.assertEqual(from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(result)))), result)
        text = self.office('Anoscopy was performed today.\nGrade 2 internal hemorrhoids, banding candidate.')
        self.assertEqual(self.other(text).status, 'performed')
        self.assertEqual(read(text, 'Grade 2 internal hemorrhoids, banding candidate.')[0], 'uncertain')

    def test_many_other_procedures_route_in_bounded_time(self):
        import time
        for body in ('Anoscopy was performed, ' * 2000, 'word ' * 30000 + 'performed.',
                     'Procedures:\n' + f'{BOX_OFF} Anoscopy\n' * 3000, f'Procedure: {BOX_OFF} anoscopy ' * 3000):
            started = time.monotonic()
            route(HEADER + body)
            self.assertLess(time.monotonic() - started, 20, body[:40])


class ScaleTests(unittest.TestCase):
    """Every new reading is bounded per span: a long single-clause line naming one family, with boxes and
    facts in every segment, routes in bounded time (it took 21 s with the fact guard unbounded)."""

    def test_a_long_boxed_line_routes_in_bounded_time(self):
        import time
        text = HEADER + 'Findings: ' + ' '.join(['colonoscopy: \u2610 biopsy of the sigmoid colon \u2612 cold snare '
                                                 'polypectomy |'] * 2000)
        started = time.monotonic()
        result = route(text)
        self.assertLess(time.monotonic() - started, 20)
        # Round 4d BOXES3 (contract-r4d section 4): the line is one box row of 140,000 characters, longer than a row is
        # ever paired (B3_ROW_CHARS) and repeating its label inside its entries: held, never read by a box (performed
        # before)
        self.assertEqual(result.finding('gi.colonoscopy').status, 'uncertain')


if __name__ == '__main__':
    unittest.main()
