"""Round 3 (gi3) scope repair: today's visit versus future follow-up (interpretations 43 and 44), and a service name
restated in parentheses (X2 of the gi3 extent investigation).

Today's office visit is established only by the document's own markers - a visit title in its head naming no other
occurrence, a heading naming today's visit, a visit statement outside plan and history, a chief complaint, reason or MDM
heading, MDM, or the visit's own time. A clinician's time ("Face-to-face time", "Physician time on the service date")
documents the time basis where its sentence frames it as E/M time, or beside a marker of today's visit outside today's
procedure text. A future occurrence named in the plan (a return visit, labs, imaging, a repeat procedure) never
establishes today's visit and is never presented as doubt about it; planned-only documents and notes with no marker
stay held. "Upper endoscopy (EGD) on 2026-11-12" names one service: what attaches to either name attaches to both.

The known cases h2-01, h2-07 and h2-08 are regressions here (fixtures/gi3/scope, their author's and the live service's
texts), and the investigation's source-reviewed variants are a corpus (corpus/gi3_scope). h2-08's E/M code is tested
through routing and its E/M facts only: its contradicted date of service is the dates repair's, and the integration
owner tests the two together. Every text is synthetic and every name fictional. Pure functions: no provider, no database.
"""
import json
import time
import unittest
from datetime import date
from pathlib import Path

from studio.gi import cues, detect, services
from studio.gi.context import extract_context
from studio.gi.detect import route, status_for_span
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode, RoutingResult, from_jsonable, to_jsonable
from studio.validation.engine import assess

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'scope'
CORPUS = Path(__file__).resolve().parent / 'corpus' / 'gi3_scope'
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'


def known(name):
    return (FIXTURES / f'{name}.txt').read_text(encoding='utf-8')


def service_date(text):
    fact = extract_context(text)['service_date']
    return date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None


def routed(text):
    """Routing as the pipeline stores it: for the document's own date, through JSON and back."""
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, service_date(text))))))


def family(text, slug):
    finding = routed(text).finding(slug)
    return finding.status if finding else None


def fact_value(text, slug, name):
    finding = routed(text).finding(slug)
    return next((f.value for f in (finding.facts if finding else ()) if f.name == name), None)


def run_engine(text, picks):
    """picks: (code, [evidence passages]). The proposals by code, and the whole result (an empty reference)."""
    codes = []
    for index, (code, passages) in enumerate(picks):
        spans = tuple(EvidenceSpan(0, text.index(p), text.index(p) + len(p), p, True) for p in passages)
        codes.append(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', evidence=spans,
                                  index=index))
    result = assess(text=text, pages=(), context=extract_context(text), routing=routed(text),
                    normalized=NormalizedResponse('replay', 'gi3-scope', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=service_date(text),
                    provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}, result


def clarified(proposal):
    return [c.fact for c in proposal.clarifications]


def status_detail(proposal):
    return next(c.detail for c in proposal.checks if c.id == 'service.status')


def clinic(title, plan, time_line='', status='Patient status: established\nPlace of service: office (POS 11)\n'):
    return (BANNER + 'Saltmarsh Valley Gastroenterology (fictional)\n' + title + '\nDate of service: 2026-10-21\n' + status
            + 'Interval history\nStable on polyethylene glycol.\nExamination\nAbdomen soft and non-tender.\nAssessment\n'
            'Chronic constipation, controlled.\nPlan\n' + plan + '\n' + (time_line + '\n' if time_line else ''))


def egd(time_line, tail='Impression\nSchatzki ring.\nPlan\nAwait pathology. Follow-up visit in 2 weeks.\n', head=''):
    return (HEADER + 'Upper endoscopy report\n' + head + 'Indication\nDysphagia.\nProcedure\nEGD: the gastroscope was '
            'advanced to the second portion of the duodenum. Cold forceps biopsies were taken from the distal '
            'esophagus.\n' + time_line + '\n' + tail)


class KnownCasesTests(unittest.TestCase):
    def test_h207_is_an_established_office_visit_on_its_face_to_face_time(self):
        for name in ('h2-07-author', 'h2-07-live'):
            text = known(name)
            with self.subTest(name):
                self.assertEqual(family(text, 'gi.office_em'), 'performed')
                self.assertEqual(fact_value(text, 'gi.office_em', 'em_basis'), 'time')
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '24')
                self.assertEqual(fact_value(text, 'gi.office_em', 'patient_status'), 'established')
                self.assertEqual(family(text, 'gi.colonoscopy'), 'historical')

    def test_h207_with_cortis_own_citations_is_ready(self):
        # the live run's selection: the heading, the results table's earlier colonoscopy and the plan's return visit
        cited = ["Purpose of today's visit", 'Colonoscopy, this practice | 2025-11-12 | Normal to the cecum, no polyps',
                 'Return in one year, or sooner if symptoms change.']
        for name in ('h2-07-author', 'h2-07-live'):
            with self.subTest(name):
                proposals, result = run_engine(known(name), [('99213', cited)])
                self.assertEqual(proposals['99213'].status, 'ready', clarified(proposals['99213']))
                self.assertNotIn('performed_status', [c.fact for c in result.clarifications])

    def test_h208_routes_the_office_visit_on_its_physician_time(self):
        # routing and E/M facts only: the code's readiness waits for the dates repair (its charge block's date)
        for name in ('h2-08-author', 'h2-08-live'):
            text = known(name)
            with self.subTest(name):
                self.assertEqual(family(text, 'gi.office_em'), 'performed')
                self.assertEqual(fact_value(text, 'gi.office_em', 'em_basis'), 'time')
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '44')
                self.assertEqual(fact_value(text, 'gi.office_em', 'setting'), 'office')

    def test_h208_with_its_date_in_conflict_is_never_ready(self):
        # the stand-in for the dates repair: without the "Assessment and plan" heading the charge block's date speaks,
        # so the date of service is a conflict - asked, and 99215 is held on that question
        for name in ('h2-08-author', 'h2-08-live'):
            text = known(name)
            stand_in = text.replace('Assessment and plan\n', '', 1)
            self.assertNotEqual(stand_in, text)
            with self.subTest(name):
                self.assertEqual(extract_context(stand_in)['service_date'].origin, 'conflict')
                proposals, result = run_engine(stand_in, [('99215', ['Surveillance ultrasound in six months.'])])
                self.assertEqual(proposals['99215'].status, 'needs_clarification')
                self.assertIn('service_date', [c.fact for c in result.clarifications])
                self.assertEqual(family(stand_in, 'gi.office_em'), 'performed')

    def test_h201_follow_up_visit_stays_planned(self):
        # "... will be discussed at the follow-up visit" presupposes a later visit; no E/M is documented today
        for name in ('h2-01-author', 'h2-01-live'):
            with self.subTest(name):
                self.assertEqual(family(known(name), 'gi.office_em'), 'planned')


class TodaysVisitByItsOwnMarkersTests(unittest.TestCase):
    def test_visit_titles_in_the_head(self):
        for title in ('Clinic note - return visit', 'Hepatology follow-up note', 'GI clinic follow-up',
                      'Return visit note', 'Gastroenterology office note', 'Note type | Clinic follow-up note',
                      'Visit type: return visit', 'Office follow-up visit', 'Outpatient gastroenterology follow-up note'):
            with self.subTest(title=title):
                self.assertEqual(family(clinic(title, 'Return in one year.'), 'gi.office_em'), 'performed')

    def test_a_heading_naming_todays_visit(self):
        for heading in ("Purpose of today's visit", 'Purpose of today\u2019s visit', "Reason for today's visit"):
            text = clinic('Gastroenterology', 'Return in one year.').replace('Interval history\n', heading + '\n'
                                                                             'Constipation follow-up.\nInterval history\n')
            with self.subTest(heading=heading):
                self.assertEqual(family(text, 'gi.office_em'), 'performed')

    def test_a_title_naming_another_occurrence_is_no_marker(self):
        # "Tentative" is no status cue of a clause: only the title's occurrence words refuse it
        for title in ('Next follow-up visit', 'Scheduled visit: return visit', 'Upcoming return visit',
                      'Previous clinic note', 'Cancelled office visit', 'Tentative return visit'):
            with self.subTest(title=title):
                self.assertNotEqual(family(clinic(title, 'Continue.'), 'gi.office_em'), 'performed')

    def test_a_title_below_the_head_is_no_marker(self):
        text = clinic('Gastroenterology', 'Continue.') + 'Addendum\n' * 12 + 'Clinic note - return visit\n'
        self.assertIsNone(family(text, 'gi.office_em'))
        heading = clinic('Gastroenterology', 'Continue.') + 'Addendum\n' * 12 + "Purpose of today's visit\n"
        self.assertEqual(family(heading, 'gi.office_em'), 'performed')  # a heading that says today, anywhere

    def test_a_follow_up_title_is_never_read_as_its_plan(self):
        # "GI clinic follow-up" opens a plan section over the header (the dates repair's binding); the title is the
        # visit's own, so the visit is not read planned from it
        text = clinic('GI clinic follow-up', 'Follow up in 3 months.', status='')
        self.assertEqual(family(text, 'gi.office_em'), 'performed')

    def test_a_title_alone_on_a_procedure_day_is_no_em(self):
        text = (BANNER + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\nProcedure\nAnoscopy was performed '
                'and two internal hemorrhoids were banded.\n')
        self.assertIsNone(family(text, 'gi.office_em'))
        purpose = (HEADER + "Colonoscopy report\nPurpose of today's visit: screening colonoscopy\nProcedure\nThe "
                   'colonoscope was advanced to the cecum. One 4 mm polyp was removed with a cold snare.\n')
        self.assertIsNone(family(purpose, 'gi.office_em'))

    def test_a_procedure_reports_follow_up_visit_stays_planned(self):
        text = HEADER + 'Procedure: EGD\nRecommendations\nFollow-up office visit in 4 weeks.'
        self.assertEqual(family(text, 'gi.office_em'), 'planned')


class ClinicianTimeTests(unittest.TestCase):
    def test_framed_or_beside_a_marker_it_is_the_visits_time(self):
        for title, line, minutes in (('Gastroenterology', 'Physician time on the service date: 44 minutes.', '44'),
                                     ('Gastroenterology', 'Face-to-face time: 24 minutes, mostly counseling.', '24'),
                                     ('Gastroenterology', 'I personally spent 30 minutes with her on the date of '
                                                          'service.', '30'),
                                     ('Clinic note - return visit', 'Face-to-face time: 24 minutes.', '24'),
                                     ('Clinic note - return visit', 'Visit time: 25 minutes.', '25'),
                                     ('Gastroenterology', 'Time on the date of the encounter: 30 minutes.', '30')):
            with self.subTest(line=line):
                text = clinic(title, 'Return in one year.', line)
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), minutes)

    def test_unframed_with_no_marker_it_is_no_time(self):
        text = clinic('Gastroenterology', 'Return in one year.', 'Face-to-face time: 24 minutes.')
        self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))

    def test_a_procedures_sedations_or_interpretations_time_is_not(self):
        for line in ('Physician time: 25 minutes.', 'Provider time for sedation: 20 minutes.',
                     'Face-to-face time with the patient and family before the procedure: 15 minutes.'):
            with self.subTest(line=line):
                self.assertNotEqual(family(egd(line), 'gi.office_em'), 'performed')
        for line in ('Physician time on the interpretation: 20 minutes.',
                     'Physician time on the date of service for the interpretation: 20 minutes.'):
            with self.subTest(line=line):
                text = (HEADER + 'High-resolution esophageal manometry interpretation\nFindings\nIneffective '
                        'motility.\n' + line + '\nPlan\nFollow up in clinic.\n')
                self.assertIsNone(family(text, 'gi.office_em'))

    def test_a_later_visits_statement_marks_no_visit_for_a_clinician_time(self):
        # the follow-up visit is a later occurrence: it never establishes today's visit, so a procedure's time beside it
        # never becomes a visit's
        for line in ('Physician time: 25 minutes.', 'Face-to-face time: 15 minutes.'):
            text = egd(line, 'Impression\nSchatzki ring. Follow-up office visit in 2 weeks.\n')
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.office_em'), 'planned')
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))

    def test_a_later_visit_is_no_marker_beside_a_clinician_time(self):
        # outside any procedure text too: a later visit's statement never establishes today's visit (interpretation 44)
        text = (BANNER + 'Saltmarsh Valley Gastroenterology (fictional)\nDate of service: 2026-10-21\nAssessment\nGERD, '
                'stable. Follow-up office visit in 4 weeks.\nFace-to-face time: 24 minutes.\n')
        self.assertEqual(family(text, 'gi.office_em'), 'planned')
        self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))

    def test_a_clinician_time_in_todays_procedure_text_is_the_procedures(self):
        # beside a marker (a reason heading, a chief complaint, a clinic title), a time written under the procedure
        # heading may be the procedure's, so it never gives the visit a basis: the visit stays held, as before
        for head in ('Reason for visit: dysphagia.\n', 'Chief complaint: dysphagia.\n'):
            text = egd('Physician time: 25 minutes.', 'Plan\nAwait pathology.\n', head)
            with self.subTest(head=head):
                self.assertEqual(family(text, 'gi.office_em'), 'uncertain')
                self.assertIsNone(fact_value(text, 'gi.office_em', 'em_basis'))
        titled = (BANNER + 'Gastroenterology clinic note\nDate of service: 2026-10-14\nProcedure\nAnoscopy was performed '
                  'and two internal hemorrhoids were banded.\nPhysician time: 25 minutes.\n')
        self.assertIsNone(family(titled, 'gi.office_em'))

    def test_one_line_of_unframed_clinician_times_is_bounded(self):
        for text in (HEADER + 'Physician time: 25 minutes, ' * 3000,
                     clinic('Clinic note - return visit', 'Return.', 'Face-to-face time: 24 minutes, ' * 3000)):
            detect._analysis.cache_clear()
            start = time.process_time()
            detect.route(text)
            self.assertLess(time.process_time() - start, 10.0)


class FutureFollowUpIsNeverDoubtTests(unittest.TestCase):
    def test_a_visit_statement_naming_a_future_or_past_service_is_the_visits(self):
        for visit in ('Office visit to discuss the colonoscopy scheduled for 2026-11-18.',
                      'Established patient office visit to review the colonoscopy done last week.'):
            text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient\n' + visit + '\nChief complaint: GI '
                    'symptoms.\nAssessment: Stable.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
            with self.subTest(visit=visit):
                proposals, _ = run_engine(text, [('99214', [visit])])
                self.assertNotIn('performed_status', clarified(proposals['99214']))
                self.assertEqual(proposals['99214'].status, 'ready')

    def test_routing_writes_the_hold_the_engine_reads(self):
        # the engine recognises routing's hold by detect.VISIT_NAMES_OTHER, never by its prose: the writer must emit it
        visit = 'Office visit to discuss the colonoscopy scheduled for 2026-11-18.'
        text = HEADER + 'Place of service: Office (POS 11)\n' + visit + '\nTotal time: 32 minutes.\n'
        start = text.index(visit)
        status, read = status_for_span(text, start, start + len(visit), date(2026, 10, 21))
        self.assertEqual(status, 'uncertain')
        self.assertEqual(read[0], detect.VISIT_NAMES_OTHER + 'planned')

    def test_a_cancelled_visit_named_with_another_service_still_holds(self):
        # a cancellation or a denial may be the visit's own: it is never read as the visit's performance
        visit = 'Office visit and colonoscopy were cancelled.'
        text = HEADER + 'Place of service: Office (POS 11)\n' + visit + '\n'
        proposals, _ = run_engine(text, [('99213', [visit])])
        self.assertNotEqual(proposals['99213'].status, 'ready')

    def test_a_visit_statement_naming_a_cancelled_service_is_held_as_before(self):
        # known limit (input -> output): only a later or an earlier occurrence of the named service (interpretation 44)
        # reads as the visit's own statement; routing's hold of a cancellation or a denial stands for the reviewer
        for visit in ('Office visit to discuss the cancelled colonoscopy.',
                      'Office visit to review the colonoscopy, which was not performed.'):
            text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient\n' + visit + '\nChief complaint: GI '
                    'symptoms.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
            with self.subTest(visit=visit):
                proposals, _ = run_engine(text, [('99214', [visit])])
                self.assertEqual((proposals['99214'].status, clarified(proposals['99214'])),
                                 ('needs_clarification', ['performed_status']))

    def test_with_no_marker_the_hold_names_no_doubt_about_today(self):
        text = clinic('Gastroenterology', 'Follow up in 3 months.')
        proposals, _ = run_engine(text, [('99213', ['Follow up in 3 months.'])])
        self.assertEqual(proposals['99213'].status, 'needs_clarification')  # held, never excluded
        self.assertIn("speaks of a later visit or service (read planned), never of today's visit",
                      status_detail(proposals['99213']))

    def test_an_earlier_visit_alone_holds_with_its_own_words(self):
        # 7c8 skeptic sk:8's shape: a reference to an earlier visit never excludes an E/M code, and never doubts today's
        text = clinic('Gastroenterology', 'Continue.') + 'Last seen by Dr. Ramos (fictional) on 2026-03-02.\n'
        proposals, _ = run_engine(text, [('99213', ['Last seen by Dr. Ramos (fictional) on 2026-03-02.'])])
        self.assertEqual(proposals['99213'].status, 'needs_clarification')
        self.assertIn("speaks of an earlier visit or service (read historical), never of today's visit",
                      status_detail(proposals['99213']))

    def test_planned_only_documents_are_never_ready(self):
        for text, line in (
                (BANNER + 'Appointment confirmation\nYour follow-up office visit is scheduled for 2026-11-18.\n',
                 'Your follow-up office visit is scheduled for 2026-11-18.'),
                (BANNER + 'Recall letter\nYou are due for your next clinic visit.\n',
                 'You are due for your next clinic visit.'),
                (BANNER + 'Scheduled visit: return visit\nAppointment date: 2026-11-18\n', 'Scheduled visit: return visit')):
            with self.subTest(line=line):
                proposals, _ = run_engine(text, [('99213', [line])])
                self.assertNotEqual(proposals['99213'].status, 'ready')

    def test_a_planned_repeat_never_doubts_todays_procedure(self):
        text = (HEADER + 'Colonoscopy report\nProcedure\nThe adult colonoscope was advanced to the cecum. One 4 mm sigmoid '
                'polyp was removed with a cold snare.\nPlan\nRepeat colonoscopy in 3 years.\n')
        proposals, _ = run_engine(text, [('45385', ['Repeat colonoscopy in 3 years.'])])
        self.assertEqual(proposals['45385'].status, 'ready')


PRE = BANNER + 'Pre-procedure note\nDate of service: 2026-10-20\nProcedures:\n'
PROCEDURE = BANNER + 'Endoscopy unit report\nDate of service: 2026-10-20\nProcedure:\n'  # its title names no service


class RestatedNameTests(unittest.TestCase):
    """X2: a service name restated in parentheses is one mention for every cue that attaches to it."""

    def test_the_summary_table_of_planned_examinations(self):
        f117 = known('f1-17')
        under_procedures = f117.replace('Procedure summary\n', 'Procedures\n', 1)
        self.assertNotEqual(under_procedures, f117)
        for text in (f117, under_procedures):
            with self.subTest(heading=text.split('\n')[7]):
                self.assertEqual(family(text, 'gi.egd'), 'planned')
                self.assertEqual(family(text, 'gi.colonoscopy'), 'planned')

    def test_the_prose_form(self):
        text = PRE + 'Upper endoscopy (EGD) on 2026-11-12.\nColonoscopy on 2026-11-12.\n'
        self.assertEqual(family(text, 'gi.egd'), 'planned')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'planned')

    def test_either_name_carries_the_time_for_both(self):
        for line, status in (('EGD (upper endoscopy) on 2026-11-12.', 'planned'),
                             ('Esophagogastroduodenoscopy (EGD) on 2026-11-12.', 'planned'),
                             ('Upper endoscopy (EGD, 2026-11-12).', 'planned'),
                             ('Upper endoscopy (EGD) in 6 weeks.', 'planned'),
                             ('Upper endoscopy (EGD) scheduled for next week.', 'planned'),
                             ('Upper endoscopy (EGD) on 2026-09-12.', 'historical'),
                             ('Upper endoscopy (EGD) 2 years ago.', 'historical'),
                             ('Upper endoscopy (EGD) and colonoscopy on 2026-11-12.', 'planned')):
            with self.subTest(line=line):
                self.assertEqual(family(PRE + line + '\n', 'gi.egd'), status)
        for line, slug in (('Endoscopic ultrasound (EUS) on 2026-11-12.', 'gi.eus'),
                           ('Endoscopic retrograde cholangiopancreatography (ERCP) on 2026-11-12.', 'gi.ercp'),
                           ('Flexible sigmoidoscopy (FS) on 2026-11-12.', 'gi.flex_sig')):
            with self.subTest(line=line):
                self.assertEqual(family(PRE + line + '\n', slug), 'planned')
        both = PRE + 'Upper endoscopy (EGD) and colonoscopy on 2026-11-12.\n'
        self.assertEqual(family(both, 'gi.colonoscopy'), 'planned')

    def test_todays_restated_service_stays_performed(self):
        for line in ('Upper endoscopy (EGD) on 2026-10-20.', 'Upper endoscopy (EGD) today.',
                     'Upper endoscopy (EGD) was performed to the second portion of the duodenum.'):
            with self.subTest(line=line):
                self.assertEqual(family(PRE + line + '\n', 'gi.egd'), 'performed')

    def test_a_restated_name_coordinated_after_its_parenthesis_shares_the_time(self):
        # "2 years ago" after the pair: each service is held (another time may date it or the other one), as the plain
        # coordination "Colonoscopy and EGD 2 years ago" is under a procedure heading - never read performed
        for line in ('Colonoscopy and upper endoscopy (EGD) 2 years ago.', 'Upper endoscopy (EGD) and colonoscopy 2 years '
                                                                          'ago.'):
            with self.subTest(line=line):
                self.assertNotEqual(family(PRE + line + '\n', 'gi.egd'), 'performed')
                self.assertNotEqual(family(PRE + line + '\n', 'gi.colonoscopy'), 'performed')

    def test_a_name_of_another_family_in_parentheses_keeps_its_own_time(self):
        text = PROCEDURE + 'Colonoscopy (EGD, 2019) to the cecum with cold snare polypectomy of a 4 mm sigmoid polyp.\n'
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertEqual(family(text, 'gi.egd'), 'historical')

    def test_a_name_after_other_words_in_parentheses_is_no_restatement(self):
        text = (PROCEDURE + 'Colonoscopy (prior colonoscopy, 2019) to the cecum with cold snare polypectomy of a 4 mm '
                'sigmoid polyp.\n')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_a_name_of_another_family_in_parentheses_is_another_service(self):
        # known limit (input -> output): "with EGD" is no restatement of the colonoscopy, and the date attaches to the
        # nearer name only, as at the installed revision - the colonoscopy reads performed under the procedure heading
        text = PRE + 'Colonoscopy (with EGD) on 2026-11-12.\n'
        self.assertEqual(family(text, 'gi.egd'), 'planned')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_restated_names_at_the_mention_limit_are_bounded(self):
        # 1,000 service mentions (settings.MAX_SERVICE_MENTIONS, what the analyze stage reads) in one clause
        text = PRE + 'Upper endoscopy (EGD), ' * 500 + 'on 2026-11-12.\n'
        detect._analysis.cache_clear()
        start = time.process_time()
        detect.route(text)
        self.assertLess(time.process_time() - start, 20.0)


class TitleCostTests(unittest.TestCase):
    def test_title_lines_are_read_in_linear_time(self):
        for text in (BANNER + ('Office ' * 50 + 'note x\n') * 4000, BANNER + 'a ' * 150000 + '\n',
                     BANNER + ('Visit type: ' + 'word ' * 6 + 'return visit - ' + 'x' * 70 + '\n') * 3000):
            start = time.process_time()
            list(cues.EM_TITLE.finditer(text))
            self.assertLess(time.process_time() - start, 5.0)


# --- the scope investigation's source-reviewed variants (corpus/gi3_scope) -------------------------------------------

def reading(text, cited):
    """What the document reads as, for the corpus: the date fact, routing's office E/M and other families, the E/M facts,
    the inventory's E/M, the cited code's status and questions, and the encounter's questions."""
    routing = routed(text)
    facts = extract_context(text)
    em = routing.finding('gi.office_em')
    proposals, result = run_engine(text, [(cited['code'], cited['evidence'])])
    proposal = proposals[cited['code']]
    inventory = services.build(text, service_date=service_date(text), routing=routing, context_facts=facts, pages=())
    return {
        'service_date': [facts['service_date'].origin, facts['service_date'].value],
        'office_em': em.status if em else None,
        'em_facts': {f.name: f.value for f in (em.facts if em else ())
                     if f.name in ('em_basis', 'time_minutes', 'patient_status', 'setting') and f.value},
        'families': {f.family: f.status for f in routing.findings if f.family != 'gi.office_em'},
        'inventory_em': [s.status for s in inventory.services if s.family == 'gi.office_em'],
        'proposal': {'code': proposal.code, 'status': proposal.status, 'questions': clarified(proposal)},
        'encounter_questions': sorted(c.fact for c in result.clarifications),
    }


def wrong_by_source(variant, got):
    """Why the reading is wrong by the variant's source review ([] when right). The investigation's verdict rules: the
    expectation says whether today's visit is documented, which facts the source leaves undocumented (a question about
    those is right), the visit's documented minutes, the procedures done today, and a date of service in conflict."""
    expected, verdict, why = variant['expected'], variant['verdict'], []
    em, proposal = got['office_em'], got['proposal']
    asked = set(proposal['questions'])
    if expected['em_today'] == 'performed':
        if em != 'performed':
            why.append(f"today's visit not read: routing office E/M = {em}")
        if 'performed_status' in asked:
            why.append('asks whether the visit was performed')
        documented = asked - set(verdict['undocumented']) - {'performed_status', 'separate_em'}
        if documented:
            why.append(f'asks documented facts: {sorted(documented)}')
        if 'separate_em' in asked and not verdict['same_day_procedure']:
            why.append('asks a separate-E/M question with no same-day procedure')
        if verdict['time_minutes'] and em == 'performed' and got['em_facts'].get('time_minutes') != verdict['time_minutes']:
            why.append(f"E/M time read as {got['em_facts'].get('time_minutes')}, source {verdict['time_minutes']}")
        if proposal['status'] == 'excluded':
            why.append('E/M code excluded')
    elif expected['em_today'] == 'not_performed':
        if em == 'performed':
            why.append('office E/M read as performed today')
        if proposal['code'].startswith('99') and proposal['status'] == 'ready':
            why.append('E/M code ready')
        for slug, status in verdict['procedures_today'].items():
            if got['families'].get(slug) != status:
                why.append(f"{slug} routed {got['families'].get(slug)}, source {status}")
        if verdict['procedures_today'] and proposal['code'].startswith('4') and proposal['status'] != 'ready':
            why.append(f"procedure code {proposal['code']} {proposal['status']}")
    else:
        if proposal['status'] == 'ready':
            why.append('ready although the source leaves the visit in doubt')
        if em == 'performed':
            why.append('office E/M read as performed though the note says the visit is in the future')
    if verdict['service_date_conflict'] and got['service_date'][0] != 'conflict':
        why.append(f"date of service read as {got['service_date']}, by the source a conflict of "
                   f"{' and '.join(verdict['service_date_conflict'])}")
    return why


class ScopeCorpusTests(unittest.TestCase):
    """Every variant reads right by its source review, except the recorded known limits, which read exactly as recorded.
    A change that fixes a known limit fails here and is recorded deliberately (remove it from known_limits.json)."""

    @classmethod
    def setUpClass(cls):
        cls.variants = json.loads((CORPUS / 'variants.json').read_text(encoding='utf-8'))['variants']
        cls.limits = json.loads((CORPUS / 'known_limits.json').read_text(encoding='utf-8'))['limits']

    def test_the_corpus_is_whole_and_synthetic(self):
        self.assertEqual(len(self.variants), 87)
        self.assertEqual(len({v['id'] for v in self.variants}), 87)
        for v in self.variants:
            self.assertTrue(v['text'].startswith('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT'), v['id'])
            for passage in v['cited']['evidence']:
                self.assertIn(passage, v['text'], v['id'])
        self.assertLessEqual(set(self.limits), {v['id'] for v in self.variants})

    def test_every_variant_reads_right_or_as_its_known_limit(self):
        for v in self.variants:
            with self.subTest(v['id']):
                got = reading(v['text'], v['cited'])
                why = wrong_by_source(v, got)
                limit = self.limits.get(v['id'])
                if limit is None:
                    self.assertEqual(why, [], f'{v["id"]} reads wrong by its source review: {got}')
                    continue
                self.assertTrue(why, f'{v["id"]} now reads right by its source: remove its known limit')
                self.assertEqual(why, limit['wrong'])
                self.assertEqual({key: got[key] for key in limit['output']}, limit['output'])

    def test_every_known_limit_has_its_reason(self):
        for vid, limit in self.limits.items():
            self.assertTrue(limit.get('reason', '').strip(), vid)
            self.assertTrue(limit.get('output'), vid)


if __name__ == '__main__':
    unittest.main()
