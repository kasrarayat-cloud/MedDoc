"""Round 3 (gi3) fix round 1, scope lens: what the independent refutation of the integrated candidate (543bae72a)
demonstrated against today's-visit and E/M-time reading (findings SCOPE-1 .. SCOPE-9), each with the reviewer's input
(a faithful synthetic copy), the output its source supports, and a control the fix must not change.

- SCOPE-1: a "Telephone follow-up note" or "Post-procedure follow-up note" title read as today's office visit, and the
  call's unframed physician time made 99212 ready (and, with no code, pushed a possible missed office visit).
- SCOPE-2: a plan's "Return visit - three months" in a short note's first lines read as the document's own title.
- SCOPE-3: a clinician time of another occasion ("this calendar month", "at the previous visit", "at the August visit",
  "last week", "since the last visit", "this week") counted as today's E/M time.
- SCOPE-4: a procedure's physician time after its impression became E/M time beside a title, and the time then kept
  the title on a procedure day.
- SCOPE-5: a booked or expected visit time ("(return visit slot)", "Expected visit time", "time allotted") read as
  time spent in a note started before the visit.
- SCOPE-6: a no-marker established-patient office note whose plan names a return office visit EXCLUDED its E/M code
  (interpretation 44: held, never excluded).
- SCOPE-7: "Total infusion time: 120 minutes." (and an "Infusion clinic note" title) made 99215 ready.
- SCOPE-8: "Office visit after the colonoscopy scheduled for 2026-11-18." read as today's visit.
- SCOPE-9: the hold text claimed no cited passage documents today's visit, and called today's call an earlier visit.

Every text is synthetic and every name fictional. Pure functions: no provider, no database.
"""
import time
import unittest

from studio.gi import detect
from studio.gi.context import extract_context
from studio.gi import services
from tests.test_repairs_gi3_scope import (BANNER, clarified, clinic, fact_value, family, routed, run_engine,
                                          service_date, status_detail)

PRACTICE = BANNER + 'Saltmarsh Valley Gastroenterology (fictional)\n'
OFFICE = 'Patient status: established\nPlace of service: office (POS 11)\n'
CALL = 'Called the patient two days after her colonoscopy. No bleeding or abdominal pain. Pathology pending.\n'


def em_status(text):
    return family(text, 'gi.office_em')


def encounter_check(result, check_id):
    return next(c for c in result.encounter_checks if c.id == check_id)


def no_code(text):
    """The encounter's checks when the provider selects no code: whether an office visit is pushed as missed."""
    _, result = run_engine(text, [])
    return result


def held(test, proposal, questions):
    test.assertEqual((proposal.status, clarified(proposal)), ('needs_clarification', questions))


# --- SCOPE-1 (and SCOPE-7's title): a title or visit statement naming no office visit ---------------------------------

A_TELEPHONE = (PRACTICE + 'Date of service: 2026-10-21\nTelephone follow-up note\n' + OFFICE + CALL
               + 'Physician time: 8 minutes.\n')
A_POST_PROCEDURE = A_TELEPHONE.replace('Telephone follow-up note', 'Post-procedure follow-up note')
A_TELEPHONE_LONG = (BANNER + '\nSaltmarsh Valley Gastroenterology (fictional)\nTelephone follow-up note\n\nPatient: Odalys '
                    'Fairweather-Nkemelu (fictional)\nDate of birth: 1961-05-17\nDate of service: 2026-10-21\nProvider: '
                    'Teodor Halvorsen-Abiola, MD (fictional)\n' + OFFICE + '\nReason for call\nPost-colonoscopy check two '
                    'days after the procedure.\n\nCall summary\nI called the patient. No bleeding, no abdominal pain, '
                    'tolerating diet. Pathology is pending; she will be contacted with results.\n\nPlan\nNo change. Call '
                    'with pathology results.\n\nPhysician time: 8 minutes.\n\nSigned: Teodor Halvorsen-Abiola, MD '
                    '(fictional), 2026-10-21 16:10\n')


class TitlesNamingNoOfficeVisitTests(unittest.TestCase):
    def test_a_telephone_or_post_procedure_follow_up_note_is_no_office_visit(self):
        # SCOPE-1: the call is no office or outpatient visit; 99212 is held asking whether the visit was performed (as
        # installed), never ready on the call's time
        for name, text, title in (('telephone', A_TELEPHONE, 'Telephone follow-up note'),
                                  ('post-procedure', A_POST_PROCEDURE, 'Post-procedure follow-up note'),
                                  ('telephone, long', A_TELEPHONE_LONG, 'Telephone follow-up note')):
            with self.subTest(name):
                self.assertIsNone(em_status(text))
                proposals, _ = run_engine(text, [('99212', [title, 'Physician time: 8 minutes.'])])
                held(self, proposals['99212'], ['performed_status', 'em_basis'])

    def test_with_no_code_no_office_visit_is_pushed_as_missed(self):
        for name, text in (('telephone', A_TELEPHONE), ('post-procedure', A_POST_PROCEDURE),
                           ('telephone, long', A_TELEPHONE_LONG)):
            with self.subTest(name):
                result = no_code(text)
                self.assertEqual(encounter_check(result, 'services.unproposed').status, 'pass')
                self.assertNotIn('office / outpatient visit', encounter_check(result, 'services.unresolved').detail)
                inventory = services.build(text, service_date=service_date(text), routing=routed(text),
                                           context_facts=extract_context(text), pages=())
                self.assertEqual([s for s in inventory.services if s.family == 'gi.office_em'], [])

    def test_a_telephone_visit_statement_is_no_office_visit(self):
        # the same call under a visit word: a telephone visit is no office visit (EM_VISIT names video and telehealth
        # visits, never telephone), so its physician time never makes the code ready
        text = A_TELEPHONE.replace('Telephone follow-up note', 'Telephone follow-up visit')
        self.assertIsNone(em_status(text))
        proposals, _ = run_engine(text, [('99212', ['Telephone follow-up visit', 'Physician time: 8 minutes.'])])
        held(self, proposals['99212'], ['performed_status', 'em_basis'])

    def test_a_remote_word_after_the_title_noun_or_as_the_visits_means(self):
        # the same call, its modality written after the title noun or the visit words, or before them after a label
        for title in ('Follow-up note - telephone', 'Clinic note - telephone encounter',
                      'Follow-up office visit by telephone', 'Office visit via telephone',
                      'Follow-up visit conducted by telephone', 'Telephone encounter: follow-up visit'):
            text = A_TELEPHONE.replace('Telephone follow-up note', title)
            with self.subTest(title=title):
                self.assertIsNone(em_status(text))
                proposals, _ = run_engine(text, [('99212', [title, 'Physician time: 8 minutes.'])])
                held(self, proposals['99212'], ['performed_status', 'em_basis'])

    def test_a_post_procedure_visit_statement_marks_no_clinician_time(self):
        # a statement that names a visit is read as installed (performed, held for its basis), but a word naming
        # another service's follow-up never lets it make the call's unframed time the office visit's
        text = A_TELEPHONE.replace('Telephone follow-up note', 'Post-procedure follow-up visit')
        self.assertEqual(em_status(text), 'performed')
        self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
        proposals, _ = run_engine(text, [('99212', ['Post-procedure follow-up visit', 'Physician time: 8 minutes.'])])
        held(self, proposals['99212'], ['em_basis'])
        visit = clinic('Post-op follow-up visit', 'Return in one year.', 'Face-to-face time: 24 minutes.')
        self.assertEqual(em_status(visit), 'performed')
        self.assertIsNone(fact_value(visit, 'gi.office_em', 'time_minutes'))

    def test_an_infusion_clinic_note_is_no_office_visit_title(self):
        # SCOPE-7's title: an infusion's own occasion
        text = clinic('Infusion clinic note', 'Return in 8 weeks.', 'Face-to-face time: 24 minutes.')
        self.assertIsNone(em_status(text))

    def test_controls_a_specialty_or_clinic_title_and_a_phone_field_still_mark_the_visit(self):
        for title in ('Hepatology follow-up note', 'IBD clinic note', 'IBD clinic note - infusion review',
                      'Office follow-up visit', 'Clinic note - return visit'):
            with self.subTest(title=title):
                text = clinic(title, 'Return in one year.', 'Face-to-face time: 24 minutes.')
                self.assertEqual(em_status(text), 'performed')
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '24')
        field = (PRACTICE + 'Practice phone: 555-0100 | Office visit\nDate of service: 2026-10-21\n' + OFFICE
                 + 'Assessment\nGERD.\nPlan\nContinue.\nFace-to-face time: 20 minutes.\n')
        proposals, _ = run_engine(field, [('99213', ['Office visit'])])
        self.assertEqual(proposals['99213'].status, 'ready')


# --- SCOPE-2: a plan's later visit in a short note's head is no title -------------------------------------------------

B_PHONE_RESULTS = (PRACTICE + OFFICE + 'Date of service: 2026-10-21\nResults discussion by telephone\nBiopsies from the '
                   'colonoscopy showed a tubular adenoma. Results reviewed with the patient by phone.\nPlan\nRepeat '
                   'colonoscopy in 3 years.\nReturn visit - three months\nPhysician time: 12 minutes.\n')
B_RESULTS_LETTER = (PRACTICE + 'Date of service: 2026-10-21\nResults letter\nDear Ms. Fable (fictional),\nYour colon '
                    'biopsies showed a tubular adenoma.\nPlan\nRepeat colonoscopy in 3 years.\n')


class PlanLineIsNoTitleTests(unittest.TestCase):
    def test_a_plans_return_visit_is_no_document_title(self):
        # SCOPE-2: "Return visit - three months" under "Plan" is the plan's later visit; the telephone results
        # discussion documents no visit today, so the code is held as installed, never ready
        self.assertIsNone(em_status(B_PHONE_RESULTS))
        proposals, _ = run_engine(B_PHONE_RESULTS, [('99212', ['Results reviewed with the patient by phone.',
                                                               'Physician time: 12 minutes.'])])
        held(self, proposals['99212'], ['performed_status', 'em_basis'])

    def test_a_results_letters_plan_visit_is_never_documented_as_performed(self):
        letter = B_RESULTS_LETTER + 'Follow-up visit, six weeks\n'
        self.assertEqual(em_status(letter), 'planned')
        proposals, _ = run_engine(letter, [('99213', ['Follow-up visit, six weeks'])])
        self.assertEqual(proposals['99213'].status, 'excluded')  # as installed: the letter documents no visit today
        self.assertNotIn('documented as performed', status_detail(proposals['99213']))
        later = B_RESULTS_LETTER + 'Return visit - three months\n'
        self.assertIsNone(em_status(later))
        proposals, _ = run_engine(later, [('99213', ['Return visit - three months'])])
        self.assertEqual(proposals['99213'].status, 'needs_clarification')
        self.assertIn('performed_status', clarified(proposals['99213']))

    def test_a_plan_labels_value_is_no_title(self):
        text = PRACTICE + 'Date of service: 2026-10-21\n' + OFFICE + 'Plan: Return visit - three months\n'
        self.assertIsNone(em_status(text))

    def test_controls_a_title_that_opens_its_own_plan_section_is_the_visits(self):
        # interpretation 42: a section opened by the document's own title governs nothing
        text = (PRACTICE + 'GI clinic follow-up\nDate of service: 2026-10-21\n' + OFFICE + 'Assessment\nGERD.\nPlan\n'
                'Continue omeprazole.\nFace-to-face time: 20 minutes.\n')
        self.assertEqual(em_status(text), 'performed')
        self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '20')


# --- SCOPE-3: a clinician time of another occasion ------------------------------------------------------------------

IBD = ('Saltmarsh Valley Gastroenterology (fictional)\nDate of service: 2026-10-21\nIBD clinic note\n' + OFFICE
       + 'Interval history\nCrohn disease in remission on ustekinumab.\nExamination\nAbdomen soft and non-tender.\n'
       'Assessment\nCrohn disease, in remission.\nPlan\nContinue ustekinumab. Return in 6 months.\n')


class TimeOfAnotherOccasionTests(unittest.TestCase):
    def test_another_occasions_time_is_never_the_visits(self):
        # SCOPE-3: the time basis is undocumented, so the code is held asking em_basis (as the no-time control is)
        for tail, code in (('Chronic care management\nPhysician time this calendar month for care coordination: 35 '
                            'minutes.\n', '99214'),
                           ('Face-to-face time at the previous visit: 40 minutes.\n', '99215'),
                           ('Face-to-face time at the August visit, mostly counseling: 40 minutes.\n', '99215')):
            text = BANNER + IBD + tail
            with self.subTest(tail=tail):
                self.assertEqual(em_status(text), 'performed')
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposals, _ = run_engine(text, [(code, ['IBD clinic note'])])
                held(self, proposals[code], ['em_basis'])
        control = BANNER + IBD
        proposals, _ = run_engine(control, [('99214', ['IBD clinic note'])])
        held(self, proposals['99214'], ['em_basis'])

    def test_the_occasion_before_in_or_right_after_the_statement(self):
        for line in ('Provider time counseling the family by phone last week: 30 minutes.',
                     'Clinician time coordinating care with surgery since the last visit: 50 minutes.',
                     'I personally spent 45 minutes this week coordinating care with the transplant center.',
                     'Physician time (counseling), previous visit: 40 minutes.',
                     'Total time at the previous visit: 40 minutes.', 'Total time at the August visit: 40 minutes.',
                     'Face-to-face time: 40 minutes at the previous visit.',
                     'At the previous visit, face-to-face time: 40 minutes.',
                     'Clinician time over the past 30 days: 60 minutes.', 'Physician time yesterday: 20 minutes.'):
            text = clinic('Clinic note - return visit', 'Continue omeprazole.', line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposals, _ = run_engine(text, [('99215', ['Clinic note - return visit'])])
                held(self, proposals['99215'], ['em_basis'])

    def test_controls_todays_time_beside_another_occasions_words_counts(self):
        # the statement's own words decide, never the rest of its sentence; a statement that says the date of the
        # encounter is that date's
        for line, minutes in (('Total time on the date of service: 40 minutes, including review of records from the '
                               'previous visit.', '40'),
                              ('Total time on the date of service, including review of the previous visit notes: 40 '
                               'minutes.', '40'),
                              ('Face-to-face time: 24 minutes, more than half of it spent counseling about diet, fluids '
                               'and the expected course.', '24'),
                              ('Next visit in 3 months; total time 25 minutes.', '25'),
                              ('Total time today: 30 minutes; return visit next month.', '30'),
                              ('Total time: 30 minutes (previous visit 45 minutes).', '30')):
            text = clinic('Clinic note - return visit', 'Return in one year.', line)
            with self.subTest(line=line):
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), minutes)
                proposals, _ = run_engine(text, [('99213', ['Clinic note - return visit'])])
                self.assertEqual(proposals['99213'].status, 'ready')

    def test_controls_a_dated_time_still_reads_by_its_date(self):
        text = clinic('Clinic note - return visit', 'Continue.', 'Face-to-face time on 2026-08-27: 40 minutes.')
        self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))


# --- SCOPE-4: a procedure's time after its report -------------------------------------------------------------------

D_FIBROSCAN = (PRACTICE + 'Hepatology clinic note\nDate of service: 2026-10-21\n' + OFFICE + 'Indication\nFatty liver.\n'
               'Procedure\nTransient elastography was performed: median stiffness 6.1 kPa, CAP 290 dB/m.\nImpression\nNo '
               'advanced fibrosis.\nPhysician time: 20 minutes.\n')
D_F05 = (BANNER + 'Date of service: 2026-10-21\nEndoscopy follow-up note\nIndication\nDysphagia.\nProcedure\nEGD: the '
         'gastroscope was advanced to the second portion of the duodenum.\nPlan\nAwait pathology. Follow-up visit in 2 '
         'weeks.\n')
EGD_LINE = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'


class ProcedureTimeAfterItsReportTests(unittest.TestCase):
    def test_an_elastographys_time_is_no_visit_time_beside_its_title(self):
        # SCOPE-4: no E/M is documented - the title over a procedure's report is no visit marker, and the physician
        # time after the impression may be the elastography's; held as installed
        self.assertIsNone(em_status(D_FIBROSCAN))
        proposals, _ = run_engine(D_FIBROSCAN, [('99213', ['Hepatology clinic note', 'Physician time: 20 minutes.'])])
        held(self, proposals['99213'], ['performed_status', 'em_basis'])

    def test_an_egds_time_never_keeps_the_title_on_the_procedure_day(self):
        # the EGD day's later visit stays the plan's (planned, the code excluded), as the module's F05 test reads it
        text = D_F05 + 'Physician time: 25 minutes.\n'
        self.assertEqual(em_status(text), 'planned')
        self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
        proposals, _ = run_engine(text, [('43235', [EGD_LINE]), ('99213', ['Endoscopy follow-up note'])])
        self.assertEqual(proposals['43235'].status, 'ready')
        self.assertEqual(proposals['99213'].status, 'excluded')
        control, _ = run_engine(D_F05, [('43235', [EGD_LINE]), ('99213', ['Endoscopy follow-up note'])])
        self.assertEqual(control['99213'].status, 'excluded')

    def test_controls_a_clinic_note_that_examines_and_assesses_keeps_its_time(self):
        # the corpus's F07: a visit with a same-day banding, its face-to-face time the visit's; held for the separate
        # E/M question only
        text = clinic('Clinic note - return visit', 'Return in one year.', 'Face-to-face time: 24 minutes.').replace(
            'Plan\n', 'Procedure\nAnoscopy was performed and two internal hemorrhoids were banded.\nPlan\n')
        self.assertEqual(em_status(text), 'performed')
        self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '24')
        proposals, _ = run_engine(text, [('99213', ['Clinic note - return visit', 'Face-to-face time: 24 minutes.'])])
        held(self, proposals['99213'], ['separate_em'])


# --- SCOPE-5: a booked visit time -----------------------------------------------------------------------------------

E_PRECHARTED = (BANNER + '\nSaltmarsh Valley Gastroenterology (fictional)\nClinic note - return visit\n\nVisit date: '
                '2026-11-18\n\nPatient: Odalys Fairweather-Nkemelu (fictional)\nPatient status: established\nSite: '
                'office, POS 11\n\nNote started in advance of the visit; to be completed on the day.\n{time}\n\nPlan\n'
                'Return visit to review laboratory results.\n')


class BookedVisitTimeTests(unittest.TestCase):
    def test_a_slot_or_an_expected_or_allotted_time_is_no_time_spent(self):
        # SCOPE-5: a pre-charted note's booked time; the known limit S2 holds the note (never ready)
        for line in ('Visit time: 30 minutes (return visit slot).', 'Expected visit time: 30 minutes.',
                     'Encounter time allotted: 30 minutes.', 'Scheduled visit time: 30 minutes.'):
            text = E_PRECHARTED.format(time=line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposals, _ = run_engine(text, [('99213', ['Clinic note - return visit',
                                                            'Return visit to review laboratory results.'])])
                self.assertEqual(proposals['99213'].status, 'needs_clarification')
                self.assertIn('em_basis', clarified(proposals['99213']))

    def test_a_booked_time_is_no_time_spent_in_any_note(self):
        # the booking words alone decide, in a note that does not say it was started before the visit (the reviewer's
        # input says so, and that statement alone refuses its times: the next test)
        for line in ('Visit time: 30 minutes (return visit slot).', 'Expected visit time: 30 minutes.',
                     'Encounter time allotted: 30 minutes.', 'Scheduled visit time: 30 minutes.'):
            text = clinic('Clinic note - return visit', 'Return in one year.', line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposals, _ = run_engine(text, [('99213', ['Clinic note - return visit'])])
                held(self, proposals['99213'], ['em_basis'])

    def test_a_note_written_before_its_visit_documents_no_time_spent(self):
        # the same class with no booking word: in a note started in advance of the visit no time can have been spent
        # yet, so its time is the booked length - "Total time" too (ready at the installed revision)
        for line in ('Visit time: 30 minutes.', 'Total time: 30 minutes.'):
            text = E_PRECHARTED.format(time=line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposals, _ = run_engine(text, [('99213', ['Clinic note - return visit',
                                                            'Return visit to review laboratory results.'])])
                self.assertEqual(proposals['99213'].status, 'needs_clarification')

    def test_controls_time_spent_beside_a_plan_or_expectation_word_counts(self):
        for line, minutes in (('Total time spent counseling about the expected course: 25 minutes.', '25'),
                              ('Visit time: 25 minutes.', '25')):
            text = clinic('Clinic note - return visit', 'Return in one year.', line)
            with self.subTest(line=line):
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), minutes)


# --- SCOPE-6: a no-marker note's later visit holds the E/M code -----------------------------------------------------

G_NOTE = (PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + 'Interval history\nStable on '
          'polyethylene glycol.\nExamination\nAbdomen soft and non-tender.\nAssessment\nChronic constipation, '
          'controlled.\nPlan\n{plan}\n')


class NoMarkerNoteIsHeldTests(unittest.TestCase):
    def test_a_plans_return_office_visit_never_excludes_todays_visit(self):
        # SCOPE-6 (interpretation 44): held asking whether the visit was performed and its basis, whatever it cites -
        # as the same note with "Follow up in 6 months." is
        text = G_NOTE.format(plan='Return office visit in 6 months.')
        for cited in ('Chronic constipation, controlled.', 'Stable on polyethylene glycol.',
                      'Return office visit in 6 months.'):
            with self.subTest(cited=cited):
                proposals, _ = run_engine(text, [('99213', [cited])])
                held(self, proposals['99213'], ['performed_status', 'em_basis'])
                detail = status_detail(proposals['99213'])
                self.assertIn('as planned (“Return office visit in 6 months.”): a later visit, which never '
                              "decides whether today's visit was performed", detail)
                self.assertNotIn('not as performed on the date of service', detail)
        control, _ = run_engine(G_NOTE.format(plan='Follow up in 6 months.'), [('99213', ['Chronic constipation, '
                                                                                          'controlled.'])])
        held(self, control['99213'], ['performed_status', 'em_basis'])

    def test_an_earlier_visit_never_excludes_it_either(self):
        text = G_NOTE.format(plan='Continue.').replace('Interval history\n', 'Interval history\nLast office visit was on '
                                                       '2026-08-27.\n')
        proposals, _ = run_engine(text, [('99213', ['Last office visit was on 2026-08-27.'])])
        held(self, proposals['99213'], ['performed_status', 'em_basis'])
        self.assertIn('an earlier visit', status_detail(proposals['99213']))

    def test_controls_a_document_with_no_encounter_or_a_procedure_day_keeps_the_exclusion(self):
        letter = BANNER + 'Appointment confirmation\nYour follow-up office visit is scheduled for 2026-11-18.\n'
        proposals, _ = run_engine(letter, [('99213', ['Your follow-up office visit is scheduled for 2026-11-18.'])])
        self.assertEqual(proposals['99213'].status, 'excluded')
        banding = G_NOTE.format(plan='Return office visit in 6 months.').replace(
            'Plan\n', 'Procedure\nAnoscopy was performed and two internal hemorrhoids were banded.\nPlan\n')
        proposals, _ = run_engine(banding, [('99213', ['Return office visit in 6 months.'])])
        self.assertEqual(proposals['99213'].status, 'excluded')
        cancelled = G_NOTE.format(plan='Continue.').replace('Interval history\n', 'Office visit cancelled.\n'
                                                            'Interval history\n')
        proposals, _ = run_engine(cancelled, [('99213', ['Office visit cancelled.'])])
        self.assertEqual(proposals['99213'].status, 'excluded')


# --- SCOPE-7: an infusion's time ------------------------------------------------------------------------------------

I_INFUSION = (PRACTICE + 'Infusion clinic note\nDate of service: 2026-10-21\n' + OFFICE + 'Diagnosis: Crohn disease.\n'
              'Infliximab 5 mg/kg IV was infused without reaction.\nTotal infusion time: 120 minutes.\n')


class InfusionTimeTests(unittest.TestCase):
    def test_an_infusion_visit_documents_no_office_visit(self):
        # SCOPE-7: the 120 minutes are the infusion's, a drug administration's own time; no E/M is documented
        self.assertIsNone(em_status(I_INFUSION))
        proposals, _ = run_engine(I_INFUSION, [('99215', ['Infusion clinic note', 'Total infusion time: 120 minutes.'])])
        held(self, proposals['99215'], ['performed_status', 'em_basis'])

    def test_an_infusions_time_is_never_the_visits_beside_a_visit_title(self):
        for line in ('Total infusion time: 120 minutes.', 'Time spent on the infusion: 120 minutes.'):
            text = clinic('IBD clinic note', 'Return in 8 weeks.', line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposals, _ = run_engine(text, [('99215', ['IBD clinic note'])])
                held(self, proposals['99215'], ['em_basis'])

    def test_controls_time_spent_discussing_an_infusion_is_the_visits(self):
        text = clinic('IBD clinic note', 'Return in 8 weeks.',
                      'Total time spent counseling about starting infliximab infusions: 40 minutes.')
        self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '40')
        proposals, _ = run_engine(text, [('99214', ['IBD clinic note'])])
        self.assertEqual(proposals['99214'].status, 'ready')


# --- SCOPE-8: a visit placed in time by the service it names --------------------------------------------------------

LETTER = PRACTICE + 'Appointment letter\nDate of service: 2026-10-21\n' + OFFICE
VISIT_AFTER = 'Office visit after the colonoscopy scheduled for 2026-11-18.'
VISIT_HEAD = PRACTICE + 'Date of service: 2026-10-21\nPlace of service: Office (POS 11)\nEstablished patient\n'
VISIT_TAIL = '\nChief complaint: GI symptoms.\nAssessment: Stable.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n'


class VisitPlacedByTheServiceItNamesTests(unittest.TestCase):
    def test_a_visit_after_a_planned_service_stays_held(self):
        # SCOPE-8: a later visit still; routing's hold stands - performed_status asked, never ready
        for visit in (VISIT_AFTER, 'Clinic visit following the EGD planned for next month.',
                      'Office visit to review the results of the colonoscopy scheduled for 2026-11-18.'):
            with self.subTest(visit=visit):
                proposals, _ = run_engine(LETTER + visit + '\n', [('99213', [visit])])
                held(self, proposals['99213'], ['performed_status', 'em_basis'])
                timed, _ = run_engine(LETTER + visit + '\nVisit time: 30 minutes.\n', [('99213', [visit])])
                held(self, timed['99213'], ['performed_status'])

    def test_a_visit_before_a_past_service_stays_held(self):
        visit = 'Office visit before the colonoscopy done last week.'
        proposals, _ = run_engine(LETTER + visit + '\nVisit time: 30 minutes.\n', [('99213', [visit])])
        held(self, proposals['99213'], ['performed_status'])

    def test_controls_a_visit_about_or_after_a_past_service_is_todays(self):
        for visit in ('Office visit to discuss the colonoscopy scheduled for 2026-11-18.',
                      'Established patient office visit to review the colonoscopy done last week.',
                      'Office visit after the colonoscopy done last week.',
                      'Office visit today; next office visit after the colonoscopy scheduled for 2026-11-18.'):
            with self.subTest(visit=visit):
                proposals, _ = run_engine(VISIT_HEAD + visit + VISIT_TAIL, [('99214', [visit])])
                self.assertEqual(proposals['99214'].status, 'ready')

    def test_controls_a_later_visits_words_beside_todays_chief_complaint(self):
        # the "after" is the next visit's, on its own line: the chief complaint documents today (the reviewer's C6)
        cited = 'Chief complaint: follow-up.\nNext office visit after the colonoscopy in 3 months.'
        text = VISIT_HEAD + cited + '\nTotal time: 25 minutes.\n'
        proposals, _ = run_engine(text, [('99213', [cited])])
        self.assertEqual(proposals['99213'].status, 'ready')


# --- SCOPE-9: the hold says what was read -----------------------------------------------------------------------------

H_RETURNS_TODAY = (PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + 'She returns today for '
                   'follow-up of constipation.\nInterval history\nStable on polyethylene glycol.\nExamination\nAbdomen soft '
                   'and non-tender.\nAssessment\nChronic constipation, controlled.\nPlan\nReturn in one year.\n')


class HoldWordingTests(unittest.TestCase):
    def test_the_hold_never_claims_what_the_other_cited_passages_document(self):
        # SCOPE-9: "She returns today ..." is cited beside the plan's line; held (no marker), with no claim about it
        proposals, _ = run_engine(H_RETURNS_TODAY, [('99213', ['She returns today for follow-up of constipation.',
                                                               'Return in one year.'])])
        held(self, proposals['99213'], ['performed_status', 'em_basis'])
        detail = status_detail(proposals['99213'])
        self.assertNotIn("no passage the code cites documents today's visit", detail)
        self.assertIn("the routing-era reading reads it as planned, which never decides today's visit", detail)

    def test_todays_call_is_never_called_an_earlier_visit(self):
        text = B_PHONE_RESULTS.replace('Return visit - three months\n', '')
        proposals, _ = run_engine(text, [('99212', ['Results reviewed with the patient by phone.',
                                                    'Physician time: 12 minutes.'])])
        detail = status_detail(proposals['99212'])
        self.assertNotIn('speaks of an earlier visit', detail)
        self.assertIn('the routing-era reading reads it as historical', detail)


# --- cost: every new read is bounded per statement ---------------------------------------------------------------------

class CostTests(unittest.TestCase):
    def assertRoutedWithin(self, text, seconds):
        detect._analysis.cache_clear()
        start = time.process_time()
        detect.route(text)
        self.assertLess(time.process_time() - start, seconds)

    def test_one_line_of_another_occasions_times_is_bounded(self):
        # each time statement's own words are read within a bounded reach, never back to its line's start
        self.assertRoutedWithin(clinic('Clinic note - return visit', 'Return.',
                                       'Face-to-face time at the previous visit: 40 minutes, ' * 3000), 10.0)
        self.assertRoutedWithin(clinic('Clinic note - return visit', 'Return.',
                                       'Expected visit time: 30 minutes (slot), ' * 3000), 10.0)

    def test_many_led_visit_statements_are_bounded(self):
        self.assertRoutedWithin(BANNER + 'Telephone follow-up visit; ' * 6000 + '\n', 10.0)


if __name__ == '__main__':
    unittest.main()
