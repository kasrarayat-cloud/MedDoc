"""GI routing (studio/gi/detect.py, sections.py, cues.py). Pure functions, synthetic text only."""
import time
import unittest
from pathlib import Path

from studio.gi.detect import ROUTING_VERSION, route, status_for_span
from studio.gi.profiles import DETECTED_FAMILIES, PROFILES
from studio.gi.sections import SECTION_KINDS, layout, split_sections
from studio.types import SERVICE_STATUSES, RoutingResult, from_jsonable, to_jsonable

FIXTURES = Path(__file__).parent / 'fixtures' / 'gi'
HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
DOS = 'Date of service: 2026-10-21\n'


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


def statuses(result: RoutingResult) -> dict[str, str]:
    return {f.family: f.status for f in result.findings}


def fact(result: RoutingResult, family: str, name: str):
    for item in result.finding(family).facts:
        if item.name == name:
            return item
    return None


def value(result: RoutingResult, family: str, name: str):
    item = fact(result, family, name)
    return item.value if item else None


class FixtureInvariantTests(unittest.TestCase):
    """Properties every result must have, checked over every development document."""

    def test_fixtures_are_synthetic_and_numerous(self):
        paths = sorted(FIXTURES.glob('*.txt'))
        self.assertGreaterEqual(len(paths), 14)
        for path in paths:
            self.assertEqual(path.read_text(encoding='utf-8').splitlines()[0], HEADER, path.name)

    def test_spans_are_exact_and_vocabularies_closed(self):
        for path in sorted(FIXTURES.glob('*.txt')):
            text = path.read_text(encoding='utf-8')
            result = route(text)
            self.assertEqual(result.version, ROUTING_VERSION)
            self.assertIn(result.document_kind, ('procedure_report', 'office_note', 'mixed', 'unknown'))
            for finding in result.findings:
                self.assertIn(finding.family, DETECTED_FAMILIES, path.name)
                self.assertIn(finding.status, SERVICE_STATUSES)
                self.assertTrue(finding.mentions)
                self.assertTrue(set(finding.missing) <= set(PROFILES[finding.family].required_facts))
                for mention in finding.mentions:
                    self.assertEqual(text[mention.span.start:mention.span.end], mention.span.text, path.name)
                    self.assertEqual(text[mention.sentence.start:mention.sentence.end], mention.sentence.text)
                    self.assertTrue(mention.sentence.start <= mention.span.start < mention.span.end <= mention.sentence.end)
                    self.assertIn(mention.status, SERVICE_STATUSES)
                    self.assertIn(mention.section, SECTION_KINDS)
                    self.assertTrue(mention.cues, f'{path.name}: {mention.span.text} has no deciding cue')
                for item in finding.facts:
                    for span in item.evidence:
                        self.assertEqual(text[span.start:span.end], span.text, f'{path.name}: {item.name}')
                    if item.origin == 'document':
                        self.assertIsNotNone(item.value)
                        self.assertTrue(item.evidence or item.name == 'tissue_sampling', item.name)

    def test_status_for_span_agrees_with_every_mention(self):
        for path in sorted(FIXTURES.glob('*.txt')):
            text = path.read_text(encoding='utf-8')
            for finding in route(text).findings:
                for mention in finding.mentions:
                    self.assertEqual(status_for_span(text, mention.span.start, mention.span.end),
                                     (mention.status, mention.cues), f'{path.name}: {mention.span.text}')

    def test_routing_is_deterministic_and_round_trips_through_json(self):
        for path in sorted(FIXTURES.glob('*.txt')):
            text = path.read_text(encoding='utf-8')
            result = route(text)
            self.assertEqual(from_jsonable(RoutingResult, to_jsonable(result)), result)
            self.assertEqual(route(text + ''), result)
            # A copy of the text that is not the cached object routes identically.
            self.assertEqual(route(''.join(list(text))), result)


class OfficeFixtureTests(unittest.TestCase):
    def test_established_visit_with_time_and_mdm(self):
        r = route(fixture('01-office-established-time-mdm.txt'))
        self.assertEqual(r.document_kind, 'office_note')
        em = r.finding('gi.office_em')
        self.assertEqual((em.status, em.missing), ('performed', ()))
        self.assertEqual(value(r, 'gi.office_em', 'setting'), 'office')
        self.assertEqual(value(r, 'gi.office_em', 'patient_status'), 'established')
        self.assertEqual(value(r, 'gi.office_em', 'em_basis'), 'time+mdm')
        self.assertEqual(value(r, 'gi.office_em', 'time_minutes'), '32')
        self.assertEqual(value(r, 'gi.office_em', 'mdm_level'), 'moderate')
        egd = r.finding('gi.egd')
        by_text = {m.span.text: m for m in egd.mentions}
        self.assertEqual(by_text['EGD'].status, 'historical')  # "Prior EGD in 2023"
        self.assertEqual(by_text['Upper endoscopy'].status, 'planned')  # "... is scheduled for 2026-11-04"
        self.assertEqual(by_text['Upper endoscopy'].section, 'plan')
        self.assertEqual(egd.status, 'historical')  # historical outranks planned when nothing was performed
        self.assertEqual(egd.facts, ())
        self.assertNotIn('gi.colonoscopy', statuses(r))

    def test_new_patient_visit(self):
        r = route(fixture('02-office-new-patient.txt'))
        self.assertEqual(r.document_kind, 'office_note')
        self.assertEqual(value(r, 'gi.office_em', 'patient_status'), 'new')
        self.assertEqual(value(r, 'gi.office_em', 'time_minutes'), '48')
        colon = r.finding('gi.colonoscopy')
        self.assertEqual([m.status for m in colon.mentions], ['negated', 'planned'])  # never had one; recommended
        self.assertEqual(colon.status, 'negated')

    def test_colonoscopy_scheduled_in_an_office_note_is_planned(self):
        r = route(fixture('09-office-colonoscopy-scheduled.txt'))
        self.assertEqual(r.document_kind, 'office_note')
        colon = r.finding('gi.colonoscopy')
        self.assertEqual(colon.status, 'planned')
        self.assertIn('planned: 2026-11-12 is after the service date', colon.mentions[0].cues)
        self.assertEqual(colon.missing, ('extent',))
        self.assertEqual(value(r, 'gi.colonoscopy', 'intent'), 'diagnostic')
        self.assertEqual(value(r, 'gi.office_em', 'mdm_level'), 'low')

    def test_prior_colonoscopy_is_historical(self):
        r = route(fixture('10-office-prior-colonoscopy.txt'))
        self.assertEqual(r.document_kind, 'office_note')
        colon = r.finding('gi.colonoscopy')
        self.assertEqual(colon.status, 'historical')
        self.assertEqual({m.status for m in colon.mentions}, {'historical'})
        self.assertIn('historical: 2019 is before the service date', colon.mentions[0].cues)
        self.assertEqual([f.name for f in colon.facts], [])

    def test_missing_context_is_listed_not_invented(self):
        r = route(fixture('16-office-missing-context.txt'))
        self.assertEqual(r.document_kind, 'office_note')
        em = r.finding('gi.office_em')
        self.assertEqual(em.status, 'performed')
        self.assertEqual(em.missing, ('setting', 'patient_status', 'em_basis'))
        self.assertEqual(em.facts, ())


class ProcedureFixtureTests(unittest.TestCase):
    def test_egd_with_cold_forceps_biopsy(self):
        r = route(fixture('03-egd-cold-forceps-biopsy.txt'))
        self.assertEqual(r.document_kind, 'procedure_report')
        self.assertEqual(statuses(r), {'gi.office_em': 'planned', 'gi.egd': 'performed'})
        self.assertEqual(value(r, 'gi.egd', 'extent'), 'second part of duodenum')
        self.assertEqual(value(r, 'gi.egd', 'interventions'), 'biopsy')
        self.assertEqual(value(r, 'gi.egd', 'location'), 'gastric antrum; gastric body')
        self.assertEqual(r.finding('gi.egd').missing, ())

    def test_egd_with_balloon_dilation_and_no_biopsy(self):
        r = route(fixture('04-egd-balloon-dilation.txt'))
        self.assertEqual(statuses(r), {'gi.egd': 'performed'})
        self.assertEqual(value(r, 'gi.egd', 'interventions'), 'dilation (balloon)')  # "No biopsies were taken"
        self.assertEqual(value(r, 'gi.egd', 'extent'), 'second part of duodenum')

    def test_screening_colonoscopy_with_cold_snare_and_biopsy(self):
        r = route(fixture('05-colonoscopy-screening-cold-snare.txt'))
        self.assertEqual(r.document_kind, 'procedure_report')
        self.assertEqual(statuses(r), {'gi.colonoscopy': 'performed'})
        self.assertEqual(value(r, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertEqual(value(r, 'gi.colonoscopy', 'interventions'), 'biopsy; cold snare')
        self.assertEqual(value(r, 'gi.colonoscopy', 'polyp_count'), '2')
        self.assertEqual(value(r, 'gi.colonoscopy', 'intent'), 'screening')
        self.assertEqual(value(r, 'gi.colonoscopy', 'prep_quality'), 'good (BBPS 8)')
        self.assertIsNone(fact(r, 'gi.colonoscopy', 'incomplete_reason'))
        indication = [m for m in r.finding('gi.colonoscopy').mentions if m.section == 'indication']
        # "Screening colonoscopy" sets intent, not status; "no prior colonoscopy" is a past negation.
        self.assertEqual([m.status for m in indication], ['uncertain', 'negated'])
        self.assertNotIn('gi.office_em', statuses(r))  # withdrawal time is not E/M time

    def test_diagnostic_colonoscopy_to_terminal_ileum(self):
        r = route(fixture('06-colonoscopy-diagnostic-ileum.txt'))
        self.assertEqual(statuses(r), {'gi.colonoscopy': 'performed'})
        self.assertEqual(value(r, 'gi.colonoscopy', 'extent'), 'terminal ileum')
        self.assertEqual(value(r, 'gi.colonoscopy', 'interventions'), 'biopsy')
        self.assertEqual(value(r, 'gi.colonoscopy', 'intent'), 'diagnostic')
        self.assertEqual(value(r, 'gi.colonoscopy', 'prep_quality'), 'excellent')

    def test_colonoscopy_stopped_at_splenic_flexure_is_incomplete_not_flex_sig(self):
        r = route(fixture('07-colonoscopy-incomplete-splenic-flexure.txt'))
        self.assertEqual(statuses(r), {'gi.colonoscopy': 'incomplete'})
        self.assertEqual(r.document_kind, 'procedure_report')
        self.assertEqual(value(r, 'gi.colonoscopy', 'extent'), 'incomplete: splenic flexure')
        self.assertEqual(value(r, 'gi.colonoscopy', 'incomplete_reason'), 'poor bowel preparation')
        self.assertEqual(value(r, 'gi.colonoscopy', 'prep_quality'), 'poor')
        self.assertEqual(value(r, 'gi.colonoscopy', 'intent'), 'surveillance')
        self.assertIsNone(fact(r, 'gi.colonoscopy', 'interventions'))

    def test_doubt_about_a_diagnosis_is_not_doubt_about_the_service(self):
        text = (DOS + 'Procedure: Colonoscopy\nFindings\nBiopsies were taken from the right colon for possible '
                'microscopic colitis, and the patient will be called with the results. The colonoscope was advanced '
                'to the cecum, and the patient will follow up in clinic.')
        result = route(text)
        self.assertEqual(value(result, 'gi.colonoscopy', 'interventions'), 'biopsy')
        self.assertEqual(value(result, 'gi.colonoscopy', 'extent'), 'cecum')

    def test_a_size_is_never_a_polyp_count(self):
        text = (DOS + 'Procedure: Colonoscopy\nFindings\nThe colonoscope was advanced to the cecum.\n'
                '12 mm sessile polyp in the sigmoid colon, removed with a hot snare.\nTwo 3 mm polyps in the rectum.')
        self.assertEqual(value(route(text), 'gi.colonoscopy', 'polyp_count'), '2')
        text = DOS + 'Procedure: Colonoscopy\nFindings\nSeveral polyps and two 4 mm polyps were removed.'
        self.assertIsNone(fact(route(text), 'gi.colonoscopy', 'polyp_count'))  # an uncounted quantity

    def test_bidirectional_same_session(self):
        r = route(fixture('08-bidirectional-egd-colonoscopy.txt'))
        self.assertEqual(r.document_kind, 'procedure_report')
        self.assertEqual(statuses(r), {'gi.egd': 'performed', 'gi.colonoscopy': 'performed'})
        self.assertEqual(value(r, 'gi.egd', 'extent'), 'second part of duodenum')
        self.assertEqual(value(r, 'gi.egd', 'interventions'), 'biopsy')
        self.assertEqual(value(r, 'gi.egd', 'location'), 'duodenum')
        self.assertEqual(value(r, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertEqual(value(r, 'gi.colonoscopy', 'interventions'), 'hot snare')  # the EGD biopsy stays with the EGD
        self.assertEqual(value(r, 'gi.colonoscopy', 'polyp_count'), '1')  # "A 12 mm ... polyp"
        self.assertEqual(value(r, 'gi.colonoscopy', 'intent'), 'diagnostic')

    def test_cancelled_before_sedation(self):
        r = route(fixture('11-colonoscopy-cancelled-before-sedation.txt'))
        colon = r.finding('gi.colonoscopy')
        # "Procedure: Colonoscopy" alone is section evidence, which the cancellation contradicts.
        self.assertEqual(colon.status, 'cancelled')
        self.assertEqual(r.document_kind, 'unknown')
        self.assertIn('cancelled', [m.status for m in colon.mentions])
        self.assertEqual(colon.missing, ('extent',))

    def test_flexible_sigmoidoscopy_to_40_cm(self):
        r = route(fixture('12-flex-sig-40cm.txt'))
        self.assertEqual(statuses(r), {'gi.flex_sig': 'performed'})
        self.assertEqual(value(r, 'gi.flex_sig', 'extent'), '40 cm')
        self.assertEqual(value(r, 'gi.flex_sig', 'interventions'), 'cold snare')

    def test_eus_with_fnb_is_not_an_egd(self):
        r = route(fixture('13-eus-pancreas-fnb.txt'))
        self.assertEqual(statuses(r), {'gi.eus': 'performed'})
        self.assertEqual(value(r, 'gi.eus', 'target'), 'pancreatic head mass')
        self.assertEqual(value(r, 'gi.eus', 'tissue_sampling'), 'FNB')

    def test_ercp_with_sphincterotomy_and_stone_extraction_is_not_an_egd(self):
        r = route(fixture('14-ercp-sphincterotomy-stones.txt'))
        self.assertEqual(statuses(r), {'gi.ercp': 'performed'})
        self.assertEqual(value(r, 'gi.ercp', 'cannulation'), 'successful')
        # "a dilated common bile duct" is a finding, not a dilation.
        self.assertEqual(value(r, 'gi.ercp', 'interventions'), 'sphincterotomy; stone extraction (balloon)')

    def test_ercp_with_failed_cannulation_is_incomplete(self):
        r = route(fixture('15-ercp-failed-cannulation.txt'))
        ercp = r.finding('gi.ercp')
        self.assertEqual(ercp.status, 'incomplete')
        self.assertEqual(value(r, 'gi.ercp', 'cannulation'), 'failed')
        self.assertIsNone(fact(r, 'gi.ercp', 'interventions'))  # "No sphincterotomy ... no stent"
        self.assertEqual(r.finding('gi.eus').status, 'planned')  # "EUS-guided rendezvous ... will be considered"
        self.assertIsNone(fact(r, 'gi.eus', 'tissue_sampling'))
        self.assertEqual(r.document_kind, 'procedure_report')


class AdversarialStatusTests(unittest.TestCase):
    def family_status(self, body, family):
        result = route(DOS + body)
        finding = result.finding(family)
        return finding.status if finding else None

    def test_negation_governs_only_its_own_service(self):
        for body in ('Procedure: EGD.\nEGD was performed; no colonoscopy was performed.',
                     'EGD was performed today, but no colonoscopy was performed today.',
                     'EGD was performed today, no colonoscopy was performed today.'):
            self.assertEqual(self.family_status(body, 'gi.egd'), 'performed', body)
            self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'negated', body)

    def test_no_colonoscopy_was_performed_today(self):
        result = route(DOS + 'Findings\nNo colonoscopy was performed today.')
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'negated'})
        self.assertEqual(result.document_kind, 'unknown')

    def test_negation_forms(self):
        for body in ('The patient did not undergo colonoscopy.', 'Colonoscopy was not performed.',
                     'The patient declined colonoscopy.', 'Findings\nThe procedure was done without colonoscopy.',
                     'Findings\nNo EGD or colonoscopy was performed.',
                     'Findings\nNo urgent inpatient colonoscopy was performed.'):
            self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'negated', body)
        self.assertEqual(self.family_status('Findings\nNo EGD or colonoscopy was performed.', 'gi.egd'), 'negated')

    def test_without_governs_the_next_noun_only(self):
        self.assertEqual(self.family_status('Colonoscopy was performed without biopsy.', 'gi.colonoscopy'), 'performed')
        result = route(DOS + 'Colonoscopy was performed without biopsy.')
        self.assertIsNone(fact(result, 'gi.colonoscopy', 'interventions'))

    def test_coordinated_services_share_a_cue(self):
        result = route(DOS + 'Assessment: dysphagia and anemia.\nEGD and colonoscopy are recommended.')
        self.assertEqual(statuses(result), {'gi.egd': 'planned', 'gi.colonoscopy': 'planned'})
        result = route(DOS + 'Upper GI endoscopy and colonoscopy were performed today.')
        self.assertEqual(statuses(result), {'gi.egd': 'performed', 'gi.colonoscopy': 'performed'})
        result = route(DOS + 'Findings\nThe colonoscopy and the EGD were discussed with the family.')
        self.assertEqual(statuses(result), {'gi.egd': 'uncertain', 'gi.colonoscopy': 'uncertain'})

    def test_dates_relative_to_the_service_date(self):
        self.assertEqual(self.family_status('Colonoscopy on 2026-11-05.', 'gi.colonoscopy'), 'planned')
        self.assertEqual(self.family_status('Colonoscopy on 2026-10-01 showed diverticulosis.', 'gi.colonoscopy'),
                         'historical')
        self.assertEqual(self.family_status('Colonoscopy on November 5, 2026 at 8 am.', 'gi.colonoscopy'), 'planned')

    def test_dates_cannot_be_judged_without_a_service_date(self):
        status, cues = status_for_span('Findings\nColonoscopy on 2026-10-21.', 9, 20)
        self.assertEqual(status, 'uncertain')
        self.assertIn('service date not established', cues[0])

    def test_a_far_date_does_not_speak_for_a_mention(self):
        body = 'Colonoscopy was performed today for surveillance of the two adenomas that were removed in 2019.'
        self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'performed')

    def test_a_cue_governs_the_nearest_group_only(self):
        result = route(DOS + 'Findings\nColonoscopy was completed and EGD is scheduled for next week.')
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'performed', 'gi.egd': 'planned'})

    def test_bare_years(self):
        self.assertEqual(self.family_status('Findings\nColonoscopy 2019: normal.', 'gi.colonoscopy'), 'historical')
        self.assertEqual(self.family_status('Findings\nColonoscopy was performed after 2000 mg of magnesium citrate.',
                                            'gi.colonoscopy'), 'performed')
        self.assertEqual(self.family_status('Findings\nColonoscopy in endoscopy room 2045 was performed.',
                                            'gi.colonoscopy'), 'performed')
        self.assertEqual(self.family_status('Colonoscopy is planned in 2031.', 'gi.colonoscopy'), 'planned')

    def test_history_cues(self):
        for body in ('History: s/p colonoscopy 2019.', 'Prior colonoscopy was normal.', 'She had a colonoscopy.',
                     'Colonoscopy five years ago was normal.', 'Past surgical history\nColonoscopy.'):
            self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'historical', body)

    def test_history_section_past_tense_is_not_today(self):
        status, _ = status_for_span(DOS + 'History of present illness\nEGD was performed and showed gastritis.',
                                    len(DOS) + 27, len(DOS) + 30)
        self.assertEqual(status, 'historical')

    def test_planned_cues(self):
        for body in ('Plan\nColonoscopy.', 'EGD will be scheduled.', 'Recommend colonoscopy in 3 years.',
                     'Consider ERCP.', 'EUS next week.', 'Referred for flexible sigmoidoscopy.',
                     'Upcoming colonoscopy.'):
            result = route(DOS + body)
            self.assertEqual({f.status for f in result.findings}, {'planned'}, body)

    def test_uncertain_cues(self):
        for body in ('May need EGD.', 'Possible ERCP.', 'Plan: Colonoscopy if needed.', 'Colonoscopy?',
                     'EGD versus EUS.', 'Assessment\nColonoscopy.'):
            result = route(DOS + body)
            self.assertEqual({f.status for f in result.findings}, {'uncertain'}, body)

    def test_may_as_a_month_is_not_a_doubt(self):
        result = route('Date of service: May 4, 2026\nColonoscopy was performed on May 4, 2026.')
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'performed'})

    def test_cancellation_and_abort(self):
        self.assertEqual(self.family_status('Colonoscopy deferred.', 'gi.colonoscopy'), 'cancelled')
        self.assertEqual(self.family_status('Colonoscopy was aborted before sedation.', 'gi.colonoscopy'), 'cancelled')
        self.assertEqual(self.family_status('Procedure: Colonoscopy\nThe colonoscopy was canceled.', 'gi.colonoscopy'),
                         'cancelled')
        body = 'Colonoscopy was aborted after the scope was advanced to the sigmoid colon.'
        self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'incomplete')

    def test_incomplete_cues(self):
        for body in ('Findings\nUnable to advance the colonoscope beyond the hepatic flexure during colonoscopy.',
                     'Impression\nIncomplete colonoscopy.',
                     'Procedure: Colonoscopy\nTechnique\nThe colonoscope was advanced to the sigmoid colon. '
                     'The procedure was terminated because of patient discomfort.'):
            self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'incomplete', body)

    def test_medication_discontinuation_is_not_an_incomplete_procedure(self):
        body = ('Procedure: Colonoscopy\nAspirin was discontinued five days before the colonoscopy, which was '
                'performed today. The colonoscope was advanced to the cecum.')
        self.assertEqual(self.family_status(body, 'gi.colonoscopy'), 'performed')

    def test_incomplete_response_to_therapy_is_not_an_incomplete_egd(self):
        body = ('Indications: EGD for incomplete response to PPI therapy.\nProcedure: EGD\nTechnique\n'
                'The gastroscope was advanced to the second part of the duodenum.')
        result = route(DOS + body)
        self.assertEqual(statuses(result), {'gi.egd': 'performed'})
        self.assertEqual(value(result, 'gi.egd', 'extent'), 'second part of duodenum')

    def test_history_beats_incomplete_and_today_beats_neither(self):
        body = 'Prior incomplete colonoscopy in 2019. Colonoscopy was completed today to the cecum.'
        result = route(DOS + body)
        self.assertEqual([m.status for m in result.finding('gi.colonoscopy').mentions], ['historical', 'performed'])
        self.assertEqual(result.finding('gi.colonoscopy').status, 'performed')

    def test_repeat_with_a_parenthetical_history(self):
        result = route(DOS + 'Plan\nRepeat colonoscopy in 5 years (last colonoscopy 2019).')
        self.assertEqual([m.status for m in result.finding('gi.colonoscopy').mentions], ['planned', 'historical'])

    def test_section_evidence_alone_for_a_named_service(self):
        result = route(DOS + 'Procedure performed: Colonoscopy\nFindings\nThe colonoscope was advanced to the cecum.')
        self.assertEqual(result.finding('gi.colonoscopy').mentions[0].cues, ('section: procedure (Procedure performed)',))
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'performed'})

    def test_consent_is_not_performance(self):
        for body in ('Informed consent for EGD was obtained.', 'Risks, benefits and alternatives of EGD were discussed.',
                     'EGD was discussed with the patient.'):
            start = (DOS + body).index('EGD')
            self.assertEqual(status_for_span(DOS + body, start, start + 3)[0], 'uncertain', body)

    def test_consent_does_not_hide_the_extent(self):
        text = (DOS + 'Procedure: Colonoscopy\nTechnique\nAfter informed consent was obtained and risks were '
                'discussed, the colonoscope was advanced to the cecum.')
        self.assertEqual(value(route(text), 'gi.colonoscopy', 'extent'), 'cecum')



class ProcedureReferenceTests(unittest.TestCase):
    """A service referred to as "the procedure" can stop it counting as performed, never make it so."""

    def test_unnamed_cancellation_contradicts_section_evidence(self):
        for body, expected in (
                ('Procedure: Colonoscopy\nThe preparation was not completed and the procedure was not started.',
                 'cancelled'),
                ('Procedure: Colonoscopy\nThe procedure was cancelled before sedation.', 'cancelled'),
                ('Procedure: Colonoscopy\nNo procedure was performed today.', 'negated')):
            result = route(DOS + body)
            self.assertEqual(statuses(result), {'gi.colonoscopy': expected}, body)
            self.assertEqual(result.document_kind, 'unknown', body)
            reference = result.finding('gi.colonoscopy').mentions[-1]
            self.assertEqual(status_for_span(DOS + body, reference.span.start, reference.span.end),
                             (reference.status, reference.cues))

    def test_an_unfinished_preparation_is_not_an_incomplete_procedure(self):
        body = ('Procedure: Colonoscopy\nThe patient was unable to complete the bowel preparation and the '
                'preparation was not completed. The procedure was cancelled.')
        self.assertEqual(statuses(route(DOS + body)), {'gi.colonoscopy': 'cancelled'})

    def test_unnamed_termination_makes_the_service_incomplete(self):
        result = route(DOS + 'Procedure: EGD\nFindings\nThe procedure was terminated because of laryngospasm.')
        self.assertEqual(statuses(result), {'gi.egd': 'incomplete'})
        self.assertEqual(result.finding('gi.egd').mentions[-1].span.text, 'procedure was terminated')

    def test_an_unnamed_reference_never_makes_a_service_performed(self):
        result = route(DOS + 'Assessment\nColonoscopy.\nFindings\nThe procedure was performed without complication.')
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'uncertain'})

    def test_reviewed_outside_reports_are_history(self):
        result = route(DOS + 'Findings\nOutside colonoscopy report reviewed: normal.')
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'historical'})
        result = route(DOS + 'Findings\nColonoscopy records were reviewed.')
        self.assertEqual(statuses(result), {'gi.colonoscopy': 'historical'})

    def test_sentence_level_evidence_spans_keep_their_negation(self):
        text = DOS + 'Findings\nNo colonoscopy was performed today.'
        start = text.index('No colonoscopy')
        self.assertEqual(status_for_span(text, start, len(text))[0], 'negated')


class ServiceNameTests(unittest.TestCase):
    def families(self, body):
        return {m.family for f in route(DOS + body).findings for m in f.mentions}

    def test_upper_endoscopy_is_never_a_colonoscopy(self):
        self.assertEqual(self.families('Upper endoscopy was performed today.'), {'gi.egd'})
        self.assertEqual(self.families('Upper GI endoscopy performed.'), {'gi.egd'})

    def test_eus_guided_belongs_to_eus(self):
        self.assertEqual(self.families('EUS-guided FNA of the pancreatic cyst was performed.'), {'gi.eus'})
        self.assertEqual(self.families('Upper endoscopic ultrasound was performed.'), {'gi.eus'})

    def test_abbreviations(self):
        self.assertEqual(self.families('EGD performed.'), {'gi.egd'})
        self.assertEqual(self.families('ERCP performed.'), {'gi.ercp'})
        self.assertEqual(self.families('EUS performed.'), {'gi.eus'})
        self.assertEqual(self.families('FS was performed to 35 cm.'), {'gi.flex_sig'})
        self.assertEqual(self.families('Flex sig to 40 cm.'), {'gi.flex_sig'})

    def test_lookalikes_are_not_services(self):
        for body in ('MRCP showed choledocholithiasis.', 'Magnetic resonance cholangiopancreatography was done.',
                     'Rigid proctosigmoidoscopy and rigid sigmoidoscopy were performed.',
                     'The colonoscope and gastroscope were cleaned.', 'Fs and fs.', 'The FS-2 form was signed.',
                     'Capsule endoscopy was performed.'):
            self.assertEqual(self.families(body), set(), body)

    def test_duodenoscope_in_an_ercp_is_not_an_egd(self):
        body = 'ERCP\nThe duodenoscope was advanced to the second part of the duodenum. Cannulation was achieved.'
        self.assertEqual(self.families(body), {'gi.ercp'})


class OfficeEmTests(unittest.TestCase):
    def test_procedure_report_history_is_not_a_separate_visit(self):
        text = (DOS + 'Chief complaint: screening.\nHistory of present illness\nAverage-risk adult.\n'
                'Examination\nLungs clear.\nProcedure: Colonoscopy\nFindings\nThe colonoscope was advanced to the cecum.')
        result = route(text)
        em = result.finding('gi.office_em')
        self.assertEqual(em.status, 'uncertain')
        self.assertIn('em_basis', em.missing)
        self.assertIn('separate office E/M service', em.mentions[0].cues[-1])
        self.assertEqual(result.document_kind, 'procedure_report')

    def test_office_visit_with_a_same_day_procedure_is_mixed(self):
        text = (DOS + 'Place of service: 11\nEstablished patient office visit.\nChief complaint\nRectal bleeding.\n'
                'Assessment\nHemorrhoids versus proctitis.\nMedical decision making\nModerate.\n'
                'Procedure: Flexible sigmoidoscopy\nFindings\nThe sigmoidoscope was advanced to 30 cm. '
                'Grade II internal hemorrhoids.')
        result = route(text)
        self.assertEqual(result.document_kind, 'mixed')
        self.assertEqual(statuses(result), {'gi.office_em': 'performed', 'gi.flex_sig': 'performed'})
        self.assertEqual(value(result, 'gi.office_em', 'em_basis'), 'mdm')
        self.assertEqual(value(result, 'gi.flex_sig', 'extent'), '30 cm')

    MIXED = (DOS + 'Place of service: 11\nEstablished patient office visit.\nChief complaint\nRectal bleeding.\n'
             'Assessment\nHemorrhoids versus proctitis.\nMedical decision making\nModerate.\n{statement}'
             'Procedure: Flexible sigmoidoscopy\nFindings\nThe sigmoidoscope was advanced to 30 cm.')

    def test_an_explicit_separately_identifiable_statement_is_a_documented_fact(self):
        statement = 'A significant, separately identifiable evaluation and management service was provided.\n'
        text = self.MIXED.format(statement=statement)
        separate = fact(route(text), 'gi.office_em', 'separate_em')
        self.assertEqual((separate.value, separate.origin), ('documented', 'document'))
        self.assertTrue(separate.evidence)
        for span in separate.evidence:
            self.assertEqual(text[span.start:span.end], span.text)
            self.assertIn('separately identifiable', span.text)

    def test_a_negated_or_planned_statement_is_not_a_separate_e_m(self):
        for statement in ('No separately identifiable E/M service was provided.\n',
                          'This was not a significant, separately identifiable service.\n',
                          'Plan\nReturn for a separately identifiable visit if symptoms persist.\n'):
            with self.subTest(statement=statement):
                self.assertIsNone(fact(route(self.MIXED.format(statement=statement)), 'gi.office_em', 'separate_em'))

    def test_no_statement_means_no_separate_e_m_fact(self):
        self.assertIsNone(fact(route(self.MIXED.format(statement='')), 'gi.office_em', 'separate_em'))

    def test_a_procedures_heading_in_an_office_note_needs_evidence(self):
        text = (DOS + 'Office visit.\nChief complaint\nReflux.\nProcedures\nColonoscopy (normal).\nAssessment\n'
                'GERD.\nMedical decision making\nLow.')
        result = route(text)
        self.assertEqual(statuses(result), {'gi.office_em': 'performed', 'gi.colonoscopy': 'uncertain'})
        self.assertEqual(result.document_kind, 'office_note')

    def test_refused_procedure(self):
        result = route(DOS + 'Procedure: EGD\nThe patient refused the procedure.')
        self.assertEqual(statuses(result), {'gi.egd': 'negated'})

    def test_procedure_times_are_not_em_time(self):
        for line in ('Total procedure time was 25 minutes.', 'Total sedation time: 18 minutes.',
                     'Withdrawal time was 9 minutes.'):
            self.assertIsNone(route(DOS + line).finding('gi.office_em'), line)

    def test_conflicting_em_time(self):
        text = DOS + 'Office visit.\nTotal time spent on the date of the encounter: 30 minutes.\nTime\nTime: 45 minutes'
        result = route(text)
        minutes = fact(result, 'gi.office_em', 'time_minutes')
        self.assertEqual((minutes.value, minutes.origin), (None, 'conflict'))
        self.assertEqual(value(result, 'gi.office_em', 'em_basis'), 'time')

    def test_planned_visit_is_not_this_visit(self):
        result = route(DOS + 'Procedure: EGD\nRecommendations\nFollow-up office visit in 4 weeks.')
        self.assertEqual(result.finding('gi.office_em').status, 'planned')
        self.assertEqual(result.document_kind, 'procedure_report')


class StatusForSpanContractTests(unittest.TestCase):
    def test_bad_spans_are_refused(self):
        text = DOS + 'Colonoscopy was performed.'
        for start, end in ((-1, 3), (5, 5), (10, 4), (0, len(text) + 1)):
            with self.assertRaises(ValueError):
                status_for_span(text, start, end)
        with self.assertRaises(TypeError):
            status_for_span(None, 0, 1)
        with self.assertRaises(TypeError):
            route(b'Colonoscopy')

    def test_interventions_and_evidence_spans(self):
        text = DOS + 'Upper endoscopy with possible biopsy and dilation is scheduled for 2026-11-04.'
        biopsy = text.index('biopsy')
        self.assertEqual(status_for_span(text, biopsy, biopsy + 6)[0], 'planned')
        text = DOS + 'Findings\nNo biopsies were taken. Biopsies were not obtained.'
        for word in ('biopsies', 'Biopsies'):
            start = text.index(word)
            self.assertEqual(status_for_span(text, start, start + len(word))[0], 'negated', word)

    def test_evidence_spans_carry_the_family_judgement(self):
        """A code's evidence in "Procedure: Colonoscopy" must not read as performed when the
        document cancels, does not evidence, or does not complete that service."""
        for name, expected in (('11-colonoscopy-cancelled-before-sedation.txt', 'cancelled'),
                               ('07-colonoscopy-incomplete-splenic-flexure.txt', 'incomplete')):
            text = fixture(name)
            start = text.index('Colonoscopy.')
            status, cues = status_for_span(text, start, start + len('Colonoscopy'))
            self.assertEqual(status, expected, name)
            self.assertEqual(cues[0], 'section: procedure (Procedure)')
        text = (DOS + 'Office visit.\nChief complaint\nReflux.\nProcedures\nColonoscopy (normal).\n'
                'Medical decision making\nLow.')
        start = text.index('Colonoscopy')
        self.assertEqual(status_for_span(text, start, start + 11)[0], 'uncertain')
        self.assertIn('without documented extent or interventions', status_for_span(text, start, start + 11)[1][-1])

    def test_intervention_evidence_in_an_incomplete_colonoscopy_reads_incomplete(self):
        text = (DOS + 'Procedure: Colonoscopy\nFindings\nThe colonoscope was advanced to the sigmoid colon; the '
                'procedure was terminated because of discomfort. A rectal polyp was removed with a cold snare.')
        start = text.index('cold snare')
        self.assertEqual(status_for_span(text, start, start + 10)[0], 'incomplete')
        self.assertEqual(statuses(route(text)), {'gi.colonoscopy': 'incomplete'})

    def test_em_documentation_spans(self):
        text = fixture('01-office-established-time-mdm.txt')
        start = text.index('one chronic illness with progression')
        self.assertEqual(status_for_span(text, start, start + 20)[0], 'performed')
        start = text.index('Total time personally spent')
        self.assertEqual(status_for_span(text, start, start + 10)[0], 'performed')

    def test_procedure_mention_inside_mdm_is_not_performed_by_the_section(self):
        text = DOS + 'Office visit.\nMedical decision making\nModerate; decision for EGD.'
        start = text.index('EGD')
        self.assertNotEqual(status_for_span(text, start, start + 3)[0], 'performed')


class SectionTests(unittest.TestCase):
    def test_headings_inline_headings_and_key_value_lines(self):
        text = ('Patient: Test Person\nProcedure date: 2026-10-21\nPROCEDURE PERFORMED:\nColonoscopy.\n'
                'Indications: Screening.\nTime: 08:42\nExtent: cecum\n2. Findings\nNormal.\nAssessment & Plan:\nNone.')
        sections = split_sections(text)
        self.assertEqual([(s.kind, s.label) for s in sections],
                         [('other', ''), ('procedure', 'procedure performed'), ('indication', 'indications'),
                          ('findings', 'findings'), ('plan', 'assessment and plan')])
        for section in sections[1:]:
            self.assertEqual(text[section.heading.start:section.heading.end], section.heading.text)
        self.assertEqual(sections[1].heading.text, 'PROCEDURE PERFORMED:')

    def test_sentences_and_clauses(self):
        text = 'Findings\nThe colonoscope was advanced to the\ncecum. Dr. Lee saw a polyp; it was removed, but bled.'
        lay = layout(text)
        self.assertEqual([text[s:e] for s, e in lay.sentences],
                         ['Findings', 'The colonoscope was advanced to the\ncecum.',
                          'Dr. Lee saw a polyp; it was removed, but bled.'])
        self.assertEqual([text[s:e] for s, e in lay.clauses][2:],
                         ['Dr. Lee saw a polyp;', 'it was removed,', 'but bled.'])

    def test_empty_text(self):
        self.assertEqual(route(''), RoutingResult(version=ROUTING_VERSION, document_kind='unknown', findings=()))
        self.assertEqual([s.kind for s in split_sections('')], ['other'])

    def test_family_titles_open_a_procedure_section_but_history_titles_do_not(self):
        self.assertEqual(layout('COLONOSCOPY REPORT\nText.').sections[0].kind, 'procedure')
        self.assertEqual(layout('Prior colonoscopy report\nText.').sections[0].kind, 'other')


class ScaleTests(unittest.TestCase):
    def test_long_documents_route_in_bounded_time(self):
        line = ' '.join(['the colonoscopy and the egd were discussed with the family at length'] * 1500)
        text = DOS + 'Assessment\n' + line
        started = time.monotonic()
        result = route(text)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual(statuses(result), {'gi.egd': 'uncertain', 'gi.colonoscopy': 'uncertain'})


if __name__ == '__main__':
    unittest.main()
