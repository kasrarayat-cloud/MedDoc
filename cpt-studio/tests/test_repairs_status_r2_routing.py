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
