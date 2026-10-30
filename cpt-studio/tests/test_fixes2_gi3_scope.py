"""Round 3 (gi3) fix round 2, scope lens: what the second independent refutation (of b6997c39d) demonstrated against
today's-visit and E/M-time reading (findings rev2-scope-01 .. -10 and -12), and the scope residual S-R1 decided must-fix
(interpretation 50(c)). Interpretation 51(d) is the rule: today's visit needs positive evidence both ways - an office E/M
is excluded only where the document positively shows that no visit took place today, and ready only where its own
markers establish both today's visit and its basis; an uncertain reading takes the safe outcome (held), and no closed
list exempts anything from the hold (51(f)).

- rev2-scope-01: a plan item or another appointment ("Labs to be completed after the visit.", "Her pelvic floor
  physiotherapy appointment has not yet taken place.") read as a pre-charted note, which dropped every time statement,
  and a SOAP note was then EXCLUDED on its plan's return visit.
- rev2-scope-02: an occasion word inside an activity's object before the minutes ("reviewing prior visit notes") refused
  the time while the same words after them did not; the SOAP note was then excluded.
- rev2-scope-03: a telephone call titled "Follow-up visit - telephone" (a dash, a parenthesis, a header field) read as
  today's office visit, and its physician time made 99212 ready.
- rev2-scope-04: a plan's "Return visit - three months" outside a plan section read as the document's title.
- rev2-scope-05: a visit statement naming a planned service ("to follow", "afterwards", "the biopsies from") released
  routing's hold in an appointment letter.
- rev2-scope-06: another occasion's time outside round 1's combinations ("the August 27 visit", "her visit in August",
  "the initial consultation", "the hospital admission", "per schedule", "standard return slot") counted as today's.
- rev2-scope-07 and 50(c) (S-R1): a study's result under a visit title (elastography, "Assessment") made the physician
  time the visit's.
- rev2-scope-08 / -09: an office note whose exam is written under "Findings", or a SOAP note, excluded on its plan's
  return visit.
- rev2-scope-10: an administration's time written outside round 1's two forms counted as E/M time.
- rev2-scope-12: known limits, pinned by input and output.
Beside each, the shapes of this fix's own self-attack (other layouts and headings, paraphrases, tables, PDF wraps).

Every text is synthetic and every name fictional. Pure functions: no provider, no database.
"""
import time
import unittest
from pathlib import Path

from studio.gi import cues, detect
from tests.test_fixes_gi3_scope import (A_TELEPHONE_LONG, D_FIBROSCAN, G_NOTE, I_INFUSION, IBD, LETTER, OFFICE, PRACTICE,
                                        VISIT_HEAD, VISIT_TAIL, em_status, held)
from tests.test_repairs_gi3_scope import (BANNER, clarified, clinic, fact_value, family, known, run_engine,
                                          status_detail)

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'scope2'

# --- the reviewer's inputs, built from the round-1 module's own (byte-identical to rev2/scope/inputs/final, checked) ---
SOAP = (PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + 'Subjective\nStable on polyethylene glycol.\n'
        'Objective\nAbdomen soft and non-tender.\nAssessment and plan\nChronic constipation, controlled. Continue '
        'polyethylene glycol. Return office visit in 6 months.\nTotal time: 30 minutes.\n')
CITED = 'Chronic constipation, controlled.'
H207 = known('h2-07-live')
H207_CITED = ["Purpose of today's visit", 'Colonoscopy, this practice | 2025-11-12 | Normal to the cecum, no polyps',
              'Return in one year, or sooner if symptoms change.']
H208 = (FIXTURES / 'rev2-h208-layout.txt').read_text(encoding='utf-8')
H208_CITED = ['Surveillance ultrasound in six months.']


def replaced(text, old, new):
    """``text`` with its one ``old`` replaced: the replacement must apply."""
    assert text.count(old) == 1, old
    return text.replace(old, new)


def status_of(text, code, passages):
    proposals, _ = run_engine(text, [(code, passages)])
    return proposals[code]


# --- rev2-scope-01: a pre-charting statement is the note's own -----------------------------------------------------------

class PreChartingIsTheNotesOwnStatementTests(unittest.TestCase):
    def test_a_plan_item_or_another_appointment_keeps_a_completed_notes_time(self):
        # the reviewer's A-01..A-03 and my own shapes: ready with the 30 minutes, as the control without the sentence
        for name, text in (
                ('A-01', replaced(SOAP, 'Stable on polyethylene glycol.', 'Stable on polyethylene glycol. Her pelvic '
                                  'floor physiotherapy appointment has not yet taken place.')),
                ('A-02', replaced(SOAP, 'Continue polyethylene glycol. ', 'Continue polyethylene glycol. Labs to be '
                                  'completed after the visit. ')),
                ('A-03', replaced(SOAP, 'Continue polyethylene glycol. ', 'Continue polyethylene glycol. Colonoscopy in '
                                  '3 years; bowel preparation to be completed on the day before the procedure. ')),
                ('own: another appointment', replaced(SOAP, 'Stable on polyethylene glycol.', 'Stable on polyethylene '
                                                      'glycol. Her colonoscopy appointment has not yet taken place.')),
                ('own: another note', replaced(SOAP, 'Stable on polyethylene glycol.', 'Stable on polyethylene glycol. '
                                               'The referral note was written before her appointment with surgery.')),
                ('own: a form', replaced(SOAP, 'Stable on polyethylene glycol.', 'Stable on polyethylene glycol. '
                                         'Questionnaire to be completed at the visit and returned.'))):
            with self.subTest(name):
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '30')
                self.assertEqual(status_of(text, '99214', [CITED]).status, 'ready')

    def test_the_known_cases_keep_their_time_beside_such_a_sentence(self):
        # A-04/A-05 (h2-07 live) and AB-h208-01/02 (h2-08's own layout)
        for name, text, code, cited, minutes in (
                ('A-04', replaced(H207, 'weight loss or abdominal pain.', 'weight loss or abdominal pain. Her pelvic floor '
                                  'physiotherapy appointment has not yet taken place.'), '99213', H207_CITED, '24'),
                ('A-05', replaced(H207, 'adjust the dose to effect. ', 'adjust the dose to effect. Stool calprotectin to be '
                                  'completed after the visit. '), '99213', H207_CITED, '24'),
                ('AB-h208-01', replaced(H208, 'Referral to transplant hepatology placed.', 'Referral to transplant '
                                        'hepatology placed; his earlier transplant clinic appointment has not yet taken '
                                        'place.'), '99215', H208_CITED, '44'),
                ('AB-h208-02', replaced(H208, 'basic metabolic panel in one week', 'basic metabolic panel to be completed '
                                        'after the visit'), '99215', H208_CITED, '44')):
            with self.subTest(name):
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), minutes)
                self.assertEqual(status_of(text, code, cited).status, 'ready')

    def test_a_note_that_says_it_precedes_its_visit_still_documents_no_time(self):
        for line in ('Note started in advance of the visit.', 'This note was prepared before the visit; to be completed '
                     'on the day.', 'The visit has not yet taken place.', 'Draft prepared for the upcoming appointment.',
                     'Pre-charting note: visit not yet occurred.', 'Pre-charting note for the return visit.'):
            text = replaced(SOAP, 'Stable on polyethylene glycol.', 'Stable on polyethylene glycol. ' + line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                self.assertNotEqual(status_of(text, '99214', [CITED]).status, 'ready')
        cell = (PRACTICE + 'Clinic note - return visit\nDate of service: 2026-10-21\n' + OFFICE + 'Status | Note started in '
                'advance of the visit\nInterval history\nStable.\nTotal time: 30 minutes.\n')
        self.assertIsNone(fact_value(cell, 'gi.office_em', 'time_minutes'))  # in a table cell too


# --- rev2-scope-02, -06, -10: a time statement's own words, wherever they stand ------------------------------------------

class TimeStatementOwnWordsTests(unittest.TestCase):
    def test_an_occasion_word_in_the_statement_never_excludes_the_visit(self):
        # rev2-scope-02 (B-01..B-05, AB-h208-03): the reader cannot tell an object's occasion from the time's, so the
        # time is no basis - held, never excluded on the plan's return visit (round 1 excluded every one)
        for name, line in (('B-01', 'Total time spent reviewing prior visit notes, examining the patient and counseling: '
                                    '30 minutes.'),
                           ('B-02', 'Time spent reviewing the labs drawn since her last visit and counseling her: 25 '
                                    'minutes.'),
                           ('B-03', 'Total time spent reviewing her diary of the past 2 weeks and counseling: 30 minutes.'),
                           ('B-04', 'Total time spent counseling regarding the expected duration of therapy: 25 minutes.'),
                           ('B-05', 'Total time spent on injection teaching and counseling: 25 minutes.'),
                           ('own: plural visits', 'Total time spent reviewing outside records from her last two visits '
                                                  'and counseling: 35 minutes.'),
                           ('own: a table row', 'Total time spent | 30 minutes | including review of the previous visit '
                                                'notes'),
                           ('own: a PDF wrap', 'Total time spent reviewing prior\nvisit notes and counseling: 30 minutes.')):
            text = replaced(SOAP, 'Total time: 30 minutes.', line)
            with self.subTest(name):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                held(self, status_of(text, '99214', [CITED]), ['performed_status', 'em_basis'])
        text = replaced(H208, 'Physician time on the service date: 44 minutes, covering review of the ultrasound and '
                        'laboratory results, the examination, discussion of diuretics and sodium restriction with the '
                        'patient and his wife, the referral and documentation.', 'Total time spent reviewing the '
                        'previous visit notes and results, examining and counseling the patient and his wife: 44 minutes.')
        self.assertNotEqual(status_of(text, '99215', H208_CITED).status, 'excluded')

    def test_the_word_order_changes_nothing(self):
        # the reviewer's minimal pair: the same object before and after the minutes reads alike
        for line in ('Total time: 30 minutes reviewing the notes of the previous visit, examining and counseling.',
                     'Total time spent reviewing the notes of the previous visit, examining and counseling: 30 minutes.'):
            with self.subTest(line=line):
                self.assertIsNone(fact_value(clinic('Clinic note - return visit', 'Return.', line), 'gi.office_em',
                                             'time_minutes'))

    def test_another_occasions_or_a_bookings_time_beside_a_title_is_no_basis(self):
        # rev2-scope-06 (E-01..E-06, H-01, H-02) and my own shapes: held asking em_basis, never ready
        for line in ('Face-to-face time at the August 27 visit: 40 minutes.', 'Face-to-face time on 8/27: 40 minutes.',
                     'Face-to-face time at her visit in August: 40 minutes.',
                     'Face-to-face time at the initial consultation: 60 minutes.',
                     'Physician time during the hospital admission: 60 minutes.',
                     'Clinician time for the e-visit last Tuesday: 15 minutes.',
                     'Face-to-face time at the Oct. 1 visit: 40 minutes.', 'Face-to-face time, first consultation: 60 '
                     'minutes.', 'Physician time during her hospital stay: 60 minutes.', 'Face-to-face time on the 27th: '
                     '40 minutes.', 'Face-to-face time at the colonoscopy visit: 30 minutes.', 'Face-to-face time | 40 '
                     'minutes | previous visit', 'Physician time over the phone: 15 minutes.',
                     # a procedure's time beside the title (never counted at 90377ec6f413; 43: never a procedure's)
                     'Physician time at the colonoscopy: 30 minutes.', 'Physician time during the EGD: 20 minutes.',
                     'Face-to-face time for the paracentesis: 30 minutes.', 'Face-to-face time during the procedure: 20 '
                     'minutes.', 'Physician time for the banding: 15 minutes.',
                     # the reviewer's misc.json OCC row: another occasion named as an assessment
                     'Physician time at the colonoscopy pre-assessment: 30 minutes.',
                     'Total time at the colonoscopy pre-assessment: 30 minutes.',
                     # an unframed clinician time with anything between its subject and its minutes
                     'Physician time for the breath test: 15 minutes.',
                     # the classes alone decide a total time (no clinician subject): a month, a day of a month, a call
                     'Total time at her visit in August: 40 minutes.', 'Total time on the 27th: 40 minutes.',
                     'Total time on the phone: 15 minutes.'):
            text = BANNER + IBD + line + '\n'
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                held(self, status_of(text, '99215', ['IBD clinic note']), ['em_basis'])
        # a framed clinician time naming a procedure (the corpus's F08 shape): no basis, and the procedure it names asks
        # whether a separate E/M was documented
        framed = BANNER + IBD + 'Physician time on the date of service: 30 minutes, including the colonoscopy.\n'
        self.assertIsNone(fact_value(framed, 'gi.office_em', 'time_minutes'))
        proposal = status_of(framed, '99215', ['IBD clinic note'])
        self.assertEqual(proposal.status, 'needs_clarification')
        self.assertIn('em_basis', clarified(proposal))
        for line in ('Visit time: 30 minutes, standard return slot.', 'Encounter time per schedule: 30 minutes.',
                     'Encounter time: 30 minutes as scheduled.', 'Visit time: 30 minutes per template.',
                     'Total time: 30 minutes, per schedule.', 'Total time: 30 minutes as scheduled.'):
            text = clinic('Clinic note - return visit', 'Return in one year.', line)
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                held(self, status_of(text, '99214', ['Clinic note - return visit']), ['em_basis'])

    def test_controls_todays_time_is_still_the_visits(self):
        for line, minutes in (('Face-to-face time: 40 minutes.', '40'), ('Face-to-face time at this visit: 40 minutes.', '40'),
                              ('Face-to-face time at this visit, including review of the previous visit notes: 40 '
                               'minutes.', '40'),
                              ('Total time on the date of the encounter, including review of the previous visit notes: '
                               '40 minutes.', '40'), ('Visit time: 25 minutes.', '25'),
                              ('Total time on the date of the encounter was 32 minutes, including review of the prior '
                               'colonoscopy report.', '32'),
                              ('Total time spent discussing the procedure, risks and alternatives: 30 minutes.', '30'),
                              ('Face-to-face time : 24 minutes, more than half of it spent couns-\neling about diet.',
                               '24'),
                              ('Total time spent on the assessment and counseling: 30 minutes.', '30')):
            text = BANNER + IBD + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), minutes)
                self.assertEqual(status_of(text, '99215', ['IBD clinic note']).status, 'ready')

    def test_an_administrations_time_is_never_the_visits(self):
        # rev2-scope-10 (J-01..J-04) and my own shapes: the administration's own time; held asking em_basis
        infused = I_INFUSION.replace('Infusion clinic note', 'IBD clinic note').replace(
            'Total infusion time: 120 minutes.\n', '')
        self.assertNotEqual(infused, I_INFUSION)
        for line in ('Total time spent administering the infusion: 120 minutes.', 'Total time: 120 minutes (infusion).',
                     'Total time in the infusion chair: 120 minutes.',
                     'Total time from start to end of infusion: 120 minutes.',
                     'Total time with the drip running: 120 minutes.', 'Total time: 120 minutes, IV infliximab.',
                     'Total time spent on the IV administration: 120 minutes.'):
            text = infused + line + '\n'
            with self.subTest(line=line):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                held(self, status_of(text, '99215', ['IBD clinic note', line]), ['em_basis'])


# --- rev2-scope-03: another modality in the head holds the office E/M ----------------------------------------------------

class AnotherModalityInTheHeadTests(unittest.TestCase):
    def test_a_telephone_call_however_its_title_or_header_writes_it(self):
        # C-00..C-04, C-06 and my own shapes: held asking whether a visit took place, never ready on the call's time
        for head in ('Follow-up visit - telephone', 'Follow-up visit (telephone)', 'Office visit - phone',
                     'Follow-up visit (audio-only)', 'Progress note - telephone call',
                     'Visit type: Follow-up visit\nVisit mode: Telephone', 'Follow-up visit, telephone',
                     'Follow-up visit [telephone]', 'Encounter type | Telephone\nVisit type | Follow-up visit',
                     'Office visit / phone call', 'Telephone\nFollow-up visit', 'Follow-up visit - portal message',
                     'TELEPHONE ENCOUNTER\nFollow-up visit'):
            text = replaced(A_TELEPHONE_LONG, 'Telephone follow-up note', head).replace('Physician time: 8 minutes.',
                                                                                       'Physician time: 12 minutes.')
            cited = head.split('\n')[-1].split(':')[-1].strip() if 'Visit type' in head else head.split('\n')[-1]
            cited = cited if cited in text else 'Follow-up visit'
            with self.subTest(head=head):
                self.assertNotEqual(em_status(text), 'performed')
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                held(self, status_of(text, '99212', [cited, 'Physician time: 12 minutes.']),
                     ['performed_status', 'em_basis'])

    def test_a_head_sentence_names_the_modality_where_it_says_today(self):
        text = (PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + 'Spoke with the patient by '
                'telephone today about her biopsy results.\nTotal time: 10 minutes.\n')
        self.assertNotEqual(status_of(text, '99212', ['Total time: 10 minutes.']).status, 'ready')

    def test_controls_contact_fields_and_a_video_visit_name_no_other_modality(self):
        note = ('Interval history\nStable.\nPhysical examination\nAbdomen soft.\nAssessment\nGERD.\nFace-to-face time: 20 '
                'minutes.\n')
        for head in ('Phone: (555) 010-0100 | Fax: (555) 010-0101\nClinic note - return visit',
                     'Clinic note - return visit\nPatient portal: enrolled', 'Practice phone: 555-0100\nClinic note - '
                     'return visit', 'Saltmarsh Valley Gastroenterology | Tel: 555-0100 | E-mail: clinic@example.org\n'
                     'Clinic note - return visit', 'Clinic note - return visit\nPhone 555-0100',
                     'Clinic note - return visit\nTelephone | 555-0100'):
            text = PRACTICE + head + '\nDate of service: 2026-10-21\n' + OFFICE + note
            with self.subTest(head=head):
                self.assertEqual(em_status(text), 'performed')
                self.assertEqual(status_of(text, '99213', ['Clinic note - return visit']).status, 'ready')
        video = PRACTICE + 'Video visit\nDate of service: 2026-10-21\n' + OFFICE + note
        self.assertEqual(em_status(video), 'performed')
        # a head sentence about another day's call is the history's, never the encounter's modality
        past = (PRACTICE + 'Clinic note - return visit\nDate of service: 2026-10-21\n' + OFFICE + 'She called by phone last '
                'week with worsening heartburn.\n' + note)
        self.assertEqual(status_of(past, '99213', ['Clinic note - return visit']).status, 'ready')

    def test_a_letter_in_the_head_holds_every_marker(self):
        # interpretation 51(d) names a letter: the planned visit's booked "Visit time" is no basis
        text = LETTER + 'Office visit to discuss the colonoscopy scheduled for 2026-11-18.\nVisit time: 30 minutes.\n'
        held(self, status_of(text, '99213', ['Office visit to discuss the colonoscopy scheduled for 2026-11-18.']),
             ['performed_status', 'em_basis'])


# --- rev2-scope-04: a plan line is no title ------------------------------------------------------------------------------

D_HEAD = (PRACTICE + OFFICE + 'Date of service: 2026-10-21\nResults discussion by telephone\nBiopsies from the colonoscopy '
          'showed a tubular adenoma. Results reviewed with the patient by phone.\n')
D_PLAIN = D_HEAD.replace(' by telephone', '').replace(' by phone', '')


class PlanLineIsNoTitleTests(unittest.TestCase):
    def test_the_reviewers_layouts(self):
        # D-01..D-04: no heading, "Disposition", "Assessment", and a "Disposition:" label
        for name, tail in (('D-01', 'Repeat colonoscopy in 3 years.\nReturn visit - three months\n'),
                           ('D-02', 'Disposition\nRepeat colonoscopy in 3 years.\nReturn visit - three months\n'),
                           ('D-03', 'Assessment\nRepeat colonoscopy in 3 years.\nReturn visit - three months\n'),
                           ('D-04', 'Repeat colonoscopy in 3 years.\nDisposition: return visit - three months\n')):
            text = D_HEAD + tail + 'Physician time: 12 minutes.\n'
            with self.subTest(name):
                held(self, status_of(text, '99212', ['Results reviewed with the patient by phone.',
                                                     'Physician time: 12 minutes.']), ['performed_status', 'em_basis'])

    def test_with_no_modality_named_the_plan_line_is_still_no_title(self):
        # my own shapes, the telephone words removed so that only the title rules decide
        for name, tail in (('an interval after the visit', 'Repeat colonoscopy in 3 years.\nFollow-up visit - 6 weeks\n'),
                           ('Disposition', 'Disposition\nRepeat colonoscopy in 3 years.\nReturn visit\n'),
                           ('Recommendations', 'Recommendations\nRepeat colonoscopy in 3 years.\nClinic follow-up - next '
                                               'spring\n'),
                           ('Impression', 'Impression\nRepeat colonoscopy in 3 years.\nReturn visit - three months\n'),
                           ('a visit statement line', 'Repeat EGD in one year.\nFollow-up clinic visit\n')):
            text = D_PLAIN + tail + 'Physician time: 12 minutes.\n'
            with self.subTest(name):
                self.assertNotEqual(em_status(text), 'performed')
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                self.assertNotEqual(status_of(text, '99212', ['Physician time: 12 minutes.']).status, 'ready')

    def test_a_title_whose_words_after_it_name_another_occasion_is_a_later_visits(self):
        # above any sentence, the words after the title noun decide alone ("Return visit - three months" is a booking)
        for title in ('Return visit - three months', 'Follow-up visit - next spring', 'Return visit - 2026 recall'):
            text = (PRACTICE + title + '\nDate of service: 2026-10-21\n' + OFFICE + 'Interval history\nStable.\n'
                    'Face-to-face time: 12 minutes.\n')
            with self.subTest(title=title):
                self.assertNotEqual(em_status(text), 'performed')
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))

    def test_controls_the_documents_own_title_above_its_content(self):
        text = clinic('Clinic note - return visit', 'Return in one year.', 'Face-to-face time: 24 minutes.')
        self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '24')


# --- rev2-scope-05: a visit naming another time's service is today's only beside today's record --------------------------

class VisitNamingAServiceTests(unittest.TestCase):
    def test_a_later_visit_in_a_letter_stays_held(self):
        # G-01..G-05 and my own shapes
        for visit in ('Office visit to follow the colonoscopy scheduled for 2026-11-18.',
                      'Colonoscopy scheduled for 2026-11-18; office visit to follow.',
                      'Colonoscopy scheduled for 2026-11-18. Office visit afterwards.',
                      'Office visit to review the biopsies from the colonoscopy scheduled for 2026-11-18.',
                      'Office visit to review the polyp histology from the colonoscopy scheduled for 2026-11-18.'):
            with self.subTest(visit=visit):
                proposal = status_of(LETTER + visit + '\nVisit time: 30 minutes.\n', '99214', [visit])
                self.assertEqual(proposal.status, 'needs_clarification')
                self.assertIn('performed_status', clarified(proposal))
        head = PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE
        for visit in ('Office visit to follow the EGD planned for next month.',
                      'EGD planned for next month, office visit afterwards.',
                      'Office visit to go over the specimens from the colonoscopy scheduled for 2026-11-18.',
                      'Office visit once the colonoscopy scheduled for 2026-11-18 is done.', 'Office visit after that.',
                      'Office visit later.', 'Office visit at a later date.', 'Office visit next month.'):
            with self.subTest(visit=visit):
                self.assertNotEqual(status_of(head + visit + '\nVisit time: 30 minutes.\n', '99214', [visit]).status,
                                    'ready')

    def test_controls_todays_visit_discussing_a_planned_service(self):
        visit = 'Office visit to discuss the colonoscopy scheduled for 2026-11-18.'
        self.assertEqual(status_of(VISIT_HEAD + visit + VISIT_TAIL, '99214', [visit]).status, 'ready')
        recorded = (PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + visit + '\nInterval '
                    'history\nStable.\nTotal time: 30 minutes.\n')
        self.assertEqual(status_of(recorded, '99214', [visit]).status, 'ready')

    def test_controls_a_visit_statement_with_no_sequence_of_its_own(self):
        # the statement is the only marker beside an unframed clinician time, so it alone makes the time the visit's
        head = PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE
        for visit in ('Follow-up office visit for abdominal pain of 3 months duration.',
                      'Established patient office visit. She will return when the biopsy results are available.',
                      'Office visit today; follow-up later.', 'Office visit later today.',
                      'Established patient office visit two weeks after her hospital discharge.'):  # a gate text's
            text = head + visit + '\nInterval history\nStable.\nFace-to-face time: 20 minutes.\n'
            with self.subTest(visit=visit):
                self.assertEqual(em_status(text), 'performed')
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '20')


# --- rev2-scope-07 and 50(c): a visit title marks a clinician time only beside the visit's own record --------------------

SR1 = (PRACTICE + 'Hepatology clinic note\nDate of service: 2026-10-14\nPatient status: established patient\nPlace of '
       'service: 11 (office)\n{body}Physician time: 20 minutes.\n')


class VisitRecordTests(unittest.TestCase):
    def test_a_studys_result_under_a_visit_title_documents_no_visit_time(self):
        # S-R1 (interpretation 50(c), the integration owner's input), F-01/F-02, D-fibroscan, and my own shapes: held,
        # never ready, never excluded - whether or not routing codes the study
        f01 = D_FIBROSCAN.replace('Impression\n', 'Assessment\n')
        f02 = D_FIBROSCAN.replace('Impression\n', 'Clinical impression\n')
        self.assertNotEqual(f01, D_FIBROSCAN)
        for name, text in (
                ('S-R1', SR1.format(body='Transient elastography today: median stiffness 6.1 kPa, CAP 290 dB/m. No '
                                         'advanced fibrosis.\n')),
                ('F-01', f01), ('F-02', f02), ('D-fibroscan', D_FIBROSCAN),
                ('own: an Assessment heading', SR1.format(body='Transient elastography today: median stiffness 6.1 '
                                                               'kPa.\nAssessment\nNo advanced fibrosis.\n')),
                ('own: an Assessment and plan label', SR1.format(body='Transient elastography today: median stiffness '
                                                                      '6.1 kPa.\nAssessment and plan: No advanced '
                                                                      'fibrosis. Repeat in one year.\n')),
                ('own: an Examination heading', SR1.format(body='Examination\nTransient elastography: median stiffness '
                                                                '6.1 kPa.\nImpression\nNo advanced fibrosis.\n')),
                ('own: a table', SR1.format(body='Transient elastography | median stiffness 6.1 kPa | CAP 290 dB/m\nNo '
                                                 'advanced fibrosis.\n')),
                ('own: an empty HPI', SR1.format(body='Liver stiffness measurement today: 6.1 kPa.\nHPI: none '
                                                      'recorded.\n'))):
            with self.subTest(name):
                self.assertIsNone(fact_value(text, 'gi.office_em', 'time_minutes'))
                proposal = status_of(text, '99213', ['Hepatology clinic note', 'Physician time: 20 minutes.'])
                self.assertEqual(proposal.status, 'needs_clarification')
                self.assertIn('em_basis', clarified(proposal))

    def test_controls_a_visit_recorded_by_its_history_or_examination(self):
        for name, body in (('HPI', 'History of present illness: Fatty liver follow-up. She has lost 4 kg.\nPlan: '
                                   'Continue the program.\n'),
                           ('SOAP', 'Subjective\nFatty liver follow-up; weight down 4 kg.\nObjective\nAbdomen soft.\n'
                                    'Assessment and plan\nImproving steatosis.\n'),
                           ('a PDF wrap', 'Interval history\nWeight down 4 kg since the\nlast visit; no abdominal pain.\n'
                                          'Physical exam\nAbdomen soft.\n')):
            text = SR1.format(body=body)
            with self.subTest(name):
                self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '20')
                self.assertEqual(status_of(text, '99213', ['Hepatology clinic note']).status, 'ready')

    def test_controls_a_procedure_day_visit_with_its_own_history_and_examination(self):
        # the corpus's F07: a heading naming today's visit, an interval history and an examination beside a banding
        text = known('h2-07-live')
        self.assertEqual(fact_value(text, 'gi.office_em', 'time_minutes'), '24')
        banding = clinic('Clinic note - return visit', 'Return in one year.', 'Face-to-face time: 24 minutes.').replace(
            'Plan\n', 'Procedure\nAnoscopy was performed and two internal hemorrhoids were banded.\nPlan\n')
        self.assertEqual(fact_value(banding, 'gi.office_em', 'time_minutes'), '24')


# --- rev2-scope-08 / -09: a later visit never excludes today's ----------------------------------------------------------

class LaterVisitNeverExcludesTests(unittest.TestCase):
    def test_an_examination_under_findings_or_a_soap_note_is_held(self):
        n01 = (PRACTICE + 'Clinic note - return visit\nDate of service: 2026-10-21\n' + OFFICE + 'Interval history\nStable '
               'on polyethylene glycol.\nFindings\nAbdomen soft and non-tender.\nImpression\nChronic constipation, '
               'controlled.\nPlan\nContinue polyethylene glycol. Return office visit in 6 months.\nFace-to-face time: 24 '
               'minutes.\n')
        soap = replaced(SOAP, 'Continue polyethylene glycol. ', '').replace('Total time: 30 minutes.\n', '')
        i02 = replaced(replaced(replaced(soap, 'Subjective\n', 'History of present illness\n'), 'Objective\n',
                                'Physical findings\n'), 'Assessment and plan\n', 'Assessment/Plan\n')
        for name, text, cited in (('N-01', n01, ['Clinic note - return visit']),
                                  ('N-02', n01, ['Clinic note - return visit', 'Face-to-face time: 24 minutes.']),
                                  ('I-01', soap, [CITED]), ('I-02', i02, [CITED]),
                                  ('own: S/O/A/P labels', PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n'
                                   + OFFICE + 'S: Stable on polyethylene glycol.\nO: Abdomen soft.\nA/P: Chronic '
                                   'constipation, controlled. Return office visit in 6 months.\n', [CITED]),
                                  ('own: no heading at all', PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n'
                                   + OFFICE + 'Chronic constipation, controlled. Return office visit in 6 months.\n',
                                   [CITED]),
                                  ('own: a historical visit', G_NOTE.format(plan='Continue.').replace(
                                      'Interval history\n', 'Interval history\nLast office visit on 2026-08-27.\n'),
                                   ['Last office visit on 2026-08-27.'])):
            with self.subTest(name):
                proposal = status_of(text, '99213', cited)
                self.assertNotEqual(proposal.status, 'excluded')
                self.assertNotIn('not as performed on the date of service', status_detail(proposal))

    def test_the_hold_claims_no_record_the_note_does_not_have(self):
        # the hold's text names the later visit and says nothing of an examination or an assessment (round 1's text did)
        text = PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + 'Return office visit in 6 months.\n'
        proposal = status_of(text, '99213', ['Return office visit in 6 months.'])
        detail = status_detail(proposal)
        self.assertIn("a later visit, which never decides whether today's visit was performed", detail)
        self.assertIn('Nothing in the document shows that no visit took place today', detail)
        self.assertNotIn('examination', detail)

    def test_controls_a_cancelled_visit_is_still_excluded(self):
        for line in ('Office visit cancelled by the patient.', 'Office visit cancelled.'):
            text = PRACTICE + 'Gastroenterology\nDate of service: 2026-10-21\n' + OFFICE + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(status_of(text, '99213', [line]).status, 'excluded')


# --- rev2-scope-12: known limits ---------------------------------------------------------------------------------------

class KnownLimitTests(unittest.TestCase):
    def test_a_post_word_title_and_another_objects_results_stay_held(self):
        # known limits (input -> output), unchanged from the installed revision: a "post-" title is refused whatever
        # follows the hyphen (EM_NOT_OFFICE), and an outcome word before a planned service holds a visit statement
        # (engine._VISIT_AFTER_ITS_OUTCOME) - both over-holds, never ready, never excluded
        for title in ('Post-transplant hepatology clinic note', 'Post-bariatric clinic note', 'Post-COVID GI clinic note'):
            text = clinic(title, 'Return in 3 months.', 'Face-to-face time: 25 minutes.')
            with self.subTest(title=title):
                held(self, status_of(text, '99213', [title]), ['performed_status', 'em_basis'])
        for visit in ('Office visit to discuss the results of the CT and the colonoscopy scheduled for 2026-11-18.',
                      'Office visit to review pathology and to discuss the colonoscopy scheduled for 2026-11-18.'):
            with self.subTest(visit=visit):
                held(self, status_of(VISIT_HEAD + visit + VISIT_TAIL, '99214', [visit]), ['performed_status'])


# --- cost: every new read is bounded per statement, line or noun ---------------------------------------------------------

class CostTests(unittest.TestCase):
    def assertRoutedWithin(self, text, seconds):
        detect._analysis.cache_clear()
        start = time.process_time()
        detect.route(text)
        self.assertLess(time.process_time() - start, seconds)

    def test_long_statements_and_lines_are_bounded(self):
        self.assertRoutedWithin(clinic('Clinic note - return visit', 'Return.', 'Total time spent reviewing the visit '
                                       'notes of the visit: 30 minutes, ' * 2500), 15.0)
        self.assertRoutedWithin(BANNER + 'Office visit afterwards, ' * 6000 + '\n', 15.0)
        self.assertRoutedWithin(BANNER + 'Visit mode: phone ' * 8000 + '\n', 15.0)
        self.assertRoutedWithin(BANNER + ('Return visit - three months\n' * 4000), 15.0)

    def test_the_new_classes_are_linear(self):
        for pattern, unit in ((cues.EM_TIME_ELSEWHEN, 'the previous ' * 1000), (cues.EM_PRECHARTED, 'note ' * 1000),
                              (cues.EM_VISIT_SEQUENCED, 'after ' * 1000), (cues.EM_TIME_BOOKED, 'expected ' * 1000)):
            start = time.process_time()
            list(pattern.finditer(unit * 40))
            self.assertLess(time.process_time() - start, 5.0)


if __name__ == '__main__':
    unittest.main()
