"""GI round 4, Wave 1 repair cycle 1, package PV1: one test class per finding of the independent refutation of
b840ae756 (EMR-1 to EMR-9, CTS-1, CTS-2), each on the refutation's own inputs, and one test per guard the repair adds
(every cycle-1 'pv1-*' mutant of ops/gi4/mutants.py names its killing test here). Declared before the code in
tests/fixtures/gi4/declarations/pv1.json (the two 2026-11-01 repair-cycle corrections). Every case is synthetic.

The rules of the cycle:
- C2 (the inline "Complexity / Level of decision making: X" label) and C1 (skipping a plan-work noun after an E/M time
  statement's activity word) release only with POSITIVE evidence of today's in-person office visit - an exam or vital
  signs with content, the document's own office setting, no not-a-visit or procedure-day word, the statement opening its
  own line under today's documentation - and are otherwise not applied at all: installed's reading stands (a refused
  label is no mention; a refused time statement keeps installed's 'planned' reading).
- C4 holds every E/M reading only on a statement of TODAY's encounter type: a head title, an encounter-type field, or a
  sentence whose subject is today's visit or the patient's attendance - never an incidental phone phrase.
- A hold never says that a basis the note states is undocumented: where C4 holds the document, the statements it held
  are its documented basis, and its cue quotes the line it rests on.
"""
import datetime as dt
import time
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio import jobs
from studio.gi import detect

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = dt.date(2026, 10, 26)
HEAD = 'Date of service: 10/26/2026\nPlace of service: office (POS 11)\nEstablished patient\n'
EXAM = 'Physical exam\nAbdomen soft, nontender.\n'


def office(title='Office visit note', cc='Heartburn.', exam=EXAM, plan='GERD. Continue omeprazole.', tail='',
           head=HEAD):
    """An office note: a title, the head fields, a chief complaint, an exam (or ``exam``), an assessment and plan."""
    return B + f'{title}\n{head}Chief complaint\n{cc}\n{exam}Assessment and plan\n{plan}\n{tail}'


def em(text, day=DAY):
    """Routing's gi.office_em finding (None when routing reads no E/M documentation)."""
    jobs.release_routing_caches()
    return next((f for f in detect.route(text, day).findings if f.family == 'gi.office_em'), None)


def facts(finding):
    return {f.name: f.value for f in (finding.facts if finding else ())}


def spans(finding):
    return [m.span.text for m in (finding.mentions if finding else ())]


def assess(text, code, quote, user_values=None):
    """``code`` citing ``quote`` through the stages the H4 battery runs (analyze child, merged facts, assess child):
    (bucket, status, {clarification fact: reason}, {check id: (status, detail)})."""
    m = battery.modules()
    values = user_values or {}
    document_facts, day, _ = m.jobs._analyze_child(text, values, 1000)
    merged = m.jobs._merged_facts(document_facts, values)
    context = m.jobs.context_facts(SimpleNamespace(facts=merged))
    _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context,
                                     battery.response(m, text, [(code, quote, 'MAY')]), m.Lookup([], {}), 'succeeded',
                                     'ok', ())
    m.jobs.release_routing_caches()
    p = next(p for p in result.proposals if p.code == code and p.bucket != 'alternative')
    return (p.bucket, p.status, {c.fact: c.reason for c in p.clarifications},
            {c.id: (c.status, c.detail) for c in p.checks})


def outcome(text, code, quote):
    bucket, status, clarifications, _ = assess(text, code, quote)
    return bucket, status, tuple(sorted(clarifications))


READY = ('selected', 'ready', ())


class CycleCase(SimpleTestCase):
    def assert_label_not_read(self, text, label):
        """C2 refused: the label is no mention and gives no level (installed's reading)."""
        finding = em(text)
        self.assertNotIn(label, spans(finding), text)
        self.assertNotIn('mdm_level', facts(finding), text)

    def assert_not_held(self, text):
        """No C4 hold: the finding reads performed and no mention carries the not-in-person cue (the time fact alone
        cannot tell, since a document C4 holds keeps its stated basis)."""
        finding = em(text)
        self.assertEqual(finding.status, 'performed', text)
        self.assertFalse([m.span.text for m in finding.mentions if m.cues and
                          m.cues[0].startswith(detect.EM_NOT_IN_PERSON)], text)
        return finding

    def assert_c4_holds(self, text, line=None):
        """C4 holds every E/M reading of the document, its cue quoting the line it rests on."""
        finding = em(text)
        self.assertIsNotNone(finding, text)
        self.assertNotIn(finding.status, ('performed', 'incomplete'), text)
        for m in finding.mentions:  # a reading that is not performed keeps installed's status (hold-only)
            self.assertNotIn(m.status, ('performed', 'incomplete'), (m.span.text, text))
        cues = {m.cues[0] for m in finding.mentions if m.cues and m.cues[0].startswith(detect.EM_NOT_IN_PERSON)}
        self.assertTrue(cues, text)
        if line is not None:
            self.assertEqual(cues, {f"{detect.EM_NOT_IN_PERSON}: '{line}'"}, text)
        return finding


# --- the findings, on the refutation's own inputs ----------------------------------------------------------------

F1A = B + ('GI Clinic Note\n' + HEAD + 'Subjective\nThe patient called to report two days of black stools. She takes iron '
           'daily.\nAssessment and plan\nLikely iron effect. Reassured.\nComplexity of decision making: low.\n')
F1B = B + ('GI Clinic Note\n' + HEAD + 'Subjective\nSpoke with the patient on phone about her biopsy results.\n'
           'Assessment and plan\nH. pylori gastritis. Quadruple therapy sent.\nComplexity of decision making: moderate.\n')
F1C = B + ('GI Clinic Note\n' + HEAD + 'Assessment and plan\nReviewed the biopsy results with the patient by telephone. '
           'H. pylori gastritis; quadruple therapy sent.\nComplexity of decision making: moderate.\n')
F1D = B + 'Telephone\n' + HEAD + 'Reviewed her biopsy results with her.\nLevel of decision making: Moderate\n'
F1E = B + ('MyChart message\n' + HEAD + 'Patient asks whether she can stop omeprazole.\nReply sent: taper over two weeks.\n'
           'Complexity of decision making: low.\n')
F1F = B + ('Interprofessional e-consult\n' + HEAD + 'Question from Dr. Synthetic (primary care): should omeprazole be stopped '
           'before her H. pylori breath test?\nAdvice: hold it for two weeks.\nComplexity of decision making: low.\n')
F1G = B + ('GI Records Review\n' + HEAD + 'Outside records from Mercy GI reviewed at the request of her primary physician.\n'
           'Assessment and plan\nIron deficiency; colonoscopy advised.\nComplexity of decision making: low.\n')


class EMR1Tests(CycleCase):
    """EMR-1: the label made telephone, portal, e-consult and records-review notes READY (installed holds each)."""

    def test_the_portal_e_consult_and_records_inputs_read_as_installed(self):
        installed = ('selected', 'needs_clarification', ('em_basis', 'performed_status'))  # measured on 80df1831d168
        for text, code, label in ((F1A, '99213', 'Complexity of decision making: low'),
                                  (F1E, '99213', 'Complexity of decision making: low'),
                                  (F1F, '99213', 'Complexity of decision making: low'),
                                  (F1G, '99213', 'Complexity of decision making: low')):
            self.assert_label_not_read(text, label)
            quote = text[text.index(label):text.index('\n', text.index(label))]
            self.assertEqual(outcome(text, code, quote), installed, text)

    def test_the_telephone_inputs_are_held_with_their_level_as_basis(self):
        # C4 holds these notes whole: the label, the visit's own statement, is held with every other E/M reading and
        # states the basis (CTS-2) - never released, and no question asks for a basis the note states
        for text, code, label, line in (
                (F1B, '99214', 'Complexity of decision making: moderate',
                 'Spoke with the patient on phone about her biopsy results.'),
                (F1C, '99214', 'Complexity of decision making: moderate',
                 'Reviewed the biopsy results with the patient by telephone. H. pylori gastritis; quadruple therapy '
                 'sent.'),
                (F1D, '99214', 'Level of decision making: Moderate', 'Telephone')):
            finding = self.assert_c4_holds(text)
            cue = next(m.cues[0] for m in finding.mentions if m.span.text == label)
            self.assertTrue(cue.startswith(f"{detect.EM_NOT_IN_PERSON}: '") and line[20:60] in cue, cue)
            self.assertEqual(facts(finding).get('mdm_level'), 'moderate', text)
            quote = text[text.index(label):text.index('\n', text.index(label))]
            self.assertEqual(outcome(text, code, quote), ('selected', 'needs_clarification', ('performed_status',)),
                             text)

    def test_a_not_a_visit_word_refuses_it_beside_an_exam(self):  # kills pv1-visit-not-a-visit
        text = office(title='GI Clinic Note', cc='Heartburn. Patient portal message reviewed.',
                      tail='Complexity of decision making: low.\n')
        self.assertEqual(detect._pv1_office_visit(detect._analysis(text, DAY)[0]), "'portal'")
        self.assert_label_not_read(text, 'Complexity of decision making: low')

    def test_the_label_is_read_only_with_the_office_visits_evidence(self):  # kills pv1-c2-office-visit
        # the label opens its line under the plan heading and no C4 statement holds the note: only the visit evidence
        # (here: no exam) refuses it
        text = office(exam='', tail='Complexity of decision making: low.\n')
        an = detect._analysis(text, DAY)[0]
        label = next(m for m in detect._em_mentions(text, an.lay) if detect._pv1_decision_label(an, m))
        self.assertIsNone(detect._pv1_statement_refused(an, label))
        self.assertIsNotNone(detect._pv1_label_refused(an, label))
        self.assert_label_not_read(text, 'Complexity of decision making: low')

    def test_a_refused_label_is_no_mention_at_all(self):  # kills pv1-c2-drop
        # a held label would add a performed_status question installed never asks, saying no documentation
        # establishes a visit that routing reads performed (the CTS-2 class)
        text = office(exam='', tail='Complexity of decision making: moderate.\n')
        self.assert_label_not_read(text, 'Complexity of decision making: moderate')
        self.assertEqual(outcome(text, '99214', 'Complexity of decision making: moderate.'),
                         ('selected', 'needs_clarification', ('em_basis',)))  # exactly installed's


class EMR2Tests(CycleCase):
    """EMR-2: no-show and cancelled visits outside C4's old list were READY through the label."""

    INPUTS = (
        (office(exam='', plan='Patient failed to show for the appointment.', tail='Complexity of decision making: low.\n'),
         'Patient failed to show for the appointment.'),
        (B + 'Office visit note\n' + HEAD + 'The patient did not come in today; appointment to be rebooked.\n'
         'Complexity of decision making: low.\n', 'The patient did not come in today; appointment to be rebooked.'),
        (B + 'Office visit note\n' + HEAD + 'Chief complaint\nHeartburn.\nThe patient cancelled the appointment this morning; '
         'it was rescheduled.\nComplexity of decision making: low.\n',
         'The patient cancelled the appointment this morning; it was rescheduled.'),
        (B + 'Office visit note\n' + HEAD + 'Chief complaint\nHeartburn.\nPatient did not keep the appointment.\n'
         'Complexity of decision making: low.\n', 'Patient did not keep the appointment.'))

    def test_held_whole_and_the_label_never_released(self):
        # under an Assessment and plan heading the label is the visit's own statement, held with the rest (its level is
        # the stated basis, CTS-2); right under a chief complaint it is no such statement and is not read (installed)
        for (text, line), kept in zip(self.INPUTS, (True, True, False, False)):
            finding = self.assert_c4_holds(text, line)
            self.assertEqual('Complexity of decision making: low' in spans(finding), kept, text)
            self.assertEqual(outcome(text, '99213', 'Complexity of decision making: low.'),
                             ('selected', 'needs_clarification',
                              ('performed_status',) if kept else ('em_basis', 'performed_status')), text)

    def test_a_label_that_is_another_notes_is_dropped_even_there(self):  # kills pv1-c2-kept-own
        text = B + ('Office visit note\n' + HEAD + 'The patient did not come in today; appointment to be rebooked.\n'
                    'Previous note:\nComplexity of decision making: high.\n')
        self.assert_c4_holds(text)
        self.assert_label_not_read(text, 'Complexity of decision making: high')


class EMR3Tests(CycleCase):
    """EMR-3: C1 skipped a plan word that was the minutes' occasion ('the scheduled visit', 'the scheduled call', 'the
    upcoming infusion visit'); only a noun of the visit's planning work is skipped now, and only with the visit's
    evidence."""

    def test_the_lens_inputs_keep_installeds_reading(self):
        for line, code in (('Total time: 15 minutes, spent on reviewing her records before the scheduled appointment, '
                            'which the patient missed.', '99212'),
                           ('Total time: 12 minutes, spent on the scheduled call with the patient about her biopsy '
                            'results.', '99212'),
                           ('Total time: 50 minutes, including the upcoming infusion visit.', '99215'),
                           ('Total time: 30 minutes, including the time that will be spent at her procedure visit.',
                            '99213')):
            text = office(tail=line + '\n')  # an office visit with its exam: C1 may apply, the occasion still governs
            self.assertNotIn('time_minutes', facts(em(text)), line)
            self.assertEqual(outcome(text, code, line), ('selected', 'needs_clarification', ('em_basis',)), line)

    def test_a_no_show_chart_preparation_is_held(self):
        text = office(exam='', cc='Reflux follow-up.\nPatient did not show.',
                      tail='Total time: 10 minutes, spent on chart preparation for the scheduled visit.\n')
        self.assert_c4_holds(text, 'Patient did not show.')

    def test_only_a_noun_of_the_visits_planning_work_is_skipped(self):  # kills pv1-c1-nouns
        for words in ('the orders', 'the referral to surgery', 'her recommendations', 'next steps'):
            text = office(tail=f'Total time: 40 minutes, covering her history, {words} and documentation.\n')
            self.assertEqual(facts(em(text)).get('time_minutes'), '40', words)
        for words in ('the scheduled visit', 'the upcoming visit', 'awaiting results', 'what we will do about the reflux',
                      'the plan', 'the booked follow-up'):  # each 'planned' on installed (measured), as here
            text = office(tail=f'Total time: 40 minutes, covering her history, {words} and documentation.\n')
            self.assertNotIn('time_minutes', facts(em(text)), words)

    def test_c1_needs_the_office_visits_evidence(self):  # kills pv1-c1-office-visit
        line = 'Total time: 45 minutes, covering her history, the orders, and documentation.'
        self.assertEqual(facts(em(office(tail=line + '\n'))).get('time_minutes'), '45')  # with its exam
        text = office(exam='', tail=line + '\n')  # no exam: installed's 'planned: orders' stands
        self.assertNotIn('time_minutes', facts(em(text)))
        self.assertEqual(outcome(text, '99214', line), ('selected', 'needs_clarification', ('em_basis',)))

    def test_c1_needs_the_statement_to_open_its_line(self):
        text = office(tail='Seen today. Total time: 45 minutes, covering her history, the orders, and documentation.\n')
        self.assertNotIn('time_minutes', facts(em(text)))


F4_EXAM = 'Physical exam\nAbdomen soft, nontender.\n'


class EMR4Tests(CycleCase):
    """EMR-4: the label read another note's level across a line break, in a history section, or beside words naming
    another visit; a label is read only where it opens its own line under today's documentation."""

    def test_the_lens_inputs_are_not_read(self):
        base = B + 'Office visit note\n' + HEAD + 'Chief complaint\nHeartburn.\n' + F4_EXAM
        for text in (base + 'Previous note:\nComplexity of decision making: high.\nAssessment and plan\nGERD, improved.\n',
                     base + 'At last visit:\nComplexity of decision making: high.\nAssessment and plan\nGERD, improved.\n',
                     base + 'Assessment and plan\nGERD, improved.\nComplexity of decision making: high. That was at her '
                            'visit in September.\n',
                     B + 'Office visit note\n' + HEAD + 'History of present illness\nShe was seen on 09/14/2026 for reflux '
                     'and omeprazole was started. Complexity of decision making: high.\nToday she reports improvement.\n'
                     + F4_EXAM + 'Assessment and plan\nGERD, improved.\n',
                     base + 'Assessment and plan\nGERD.\nComplexity of decision making: high, per prior note.\n',
                     base + 'Previous note: complexity of decision making: high.\nAssessment and plan\nGERD, improved.\n'):
            label = 'omplexity of decision making: high'
            finding = em(text)
            self.assertFalse([s for s in spans(finding) if label in s], text)
            self.assertNotIn('mdm_level', facts(finding), text)

    def test_the_label_must_open_its_line(self):  # kills pv1-c2-opens-line
        self.assert_label_not_read(office(tail='Seen today. Complexity of decision making: low.\n'),
                                   'Complexity of decision making: low')
        for line, level in (('- Complexity of decision making: low.', 'low'),
                            ('2. Level of decision making: moderate.', 'moderate')):
            self.assertEqual(facts(em(office(tail=line + '\n'))).get('mdm_level'), level, line)

    def test_a_label_in_a_history_section_is_not_read(self):  # kills pv1-c2-history-section
        text = B + 'Office visit note\n' + HEAD + 'HPI\nComplexity of decision making: high.\n' + EXAM + \
            'Assessment and plan\nGERD.\n'
        an = detect._analysis(text, DAY)[0]
        self.assertEqual(an.lay.section_at(text.index('Complexity')).kind, 'history')
        self.assert_label_not_read(text, 'Complexity of decision making: high')

    def test_a_governing_line_naming_another_occasion_refuses_it(self):  # kills pv1-c2-governing
        for heading in ('Addendum 10/30/2026', 'Visit 09/14/2026', 'Prior visit'):
            text = office(tail=f'{heading}\nComplexity of decision making: high.\n')
            self.assert_label_not_read(text, 'Complexity of decision making: high')

    def test_a_heading_of_another_occurrence_further_up_its_section_refuses_it(self):  # kills pv1-c2-section-heading
        # a prior note pasted below today's assessment, its heading more than six lines above its label
        pasted = ('\nPrior office note from September\nShe was seen for reflux.\nOmeprazole was started.\nLine three.\n'
                  'Line four.\nLine five.\nLine six.\nLine seven.\nComplexity of decision making: high.\n')
        text = office(tail='Complexity of decision making: low.\n' + pasted)
        finding = em(text)
        self.assertEqual(facts(finding).get('mdm_level'), 'low')  # today's label is read, the pasted one is not
        self.assertNotIn('Complexity of decision making: high', spans(finding))
        self.assert_label_not_read(office(tail=pasted), 'Complexity of decision making: high')

    def test_the_rest_of_its_line_naming_another_visit_refuses_it(self):  # kills pv1-c2-line-rest
        for rest in (', per prior note.', ' (at last visit).', ', from the prior visit.', ' as of 09/14/2026.'):
            text = office(tail=f'Complexity of decision making: high{rest}\n')
            self.assert_label_not_read(text, 'Complexity of decision making: high')
        # a comparison states today's level
        self.assertEqual(facts(em(office(tail='Complexity of decision making: high, as at her prior visit.\n')))
                         .get('mdm_level'), 'high')


class EMR5Tests(CycleCase):
    """EMR-5: a procedure-day H&P taken in the endoscopy unit was READY as an office E/M through the label."""

    F5 = B + ('Endoscopy unit H&P\nDate of service: 10/20/2026\nPlace of service: office (POS 11)\nEstablished patient\n'
              'Indication: screening colonoscopy, scheduled for this morning.\nASA II. Airway class 2.\nProceed with '
              'colonoscopy.\nComplexity of decision making: low.\n')

    def test_the_lens_input_reads_as_installed(self):
        self.assert_label_not_read(self.F5, 'Complexity of decision making: low')
        self.assertEqual(outcome(self.F5, '99213', 'Complexity of decision making: low.'),
                         ('selected', 'needs_clarification', ('em_basis', 'performed_status')))

    def test_procedure_day_words_refuse_it_even_beside_an_exam(self):  # kills pv1-visit-procedure-day
        for words in ('ASA II. Airway class 2.', 'Seen prior to today\'s colonoscopy.', 'Day of procedure assessment.',
                      'Colonoscopy is scheduled for this morning.', 'NPO since midnight.'):
            text = office(cc=f'Heartburn. {words}', tail='Complexity of decision making: low.\n')
            self.assert_label_not_read(text, 'Complexity of decision making: low')

    def test_a_note_written_around_a_procedure_is_no_office_visit(self):  # kills pv1-visit-around-title
        text = office(title='Patient education note', tail='Complexity of decision making: low.\n')
        self.assertEqual(detect._pv1_office_visit(detect._analysis(text, DAY)[0]), 'a note written around a procedure')
        self.assert_label_not_read(text, 'Complexity of decision making: low')


class EMR6Tests(CycleCase):
    """EMR-6: an incidental phone or no-show phrase held correct in-person visits; C4 now holds only on a statement of
    today's encounter type."""

    def test_the_lens_inputs_are_ready_as_installed(self):
        time30 = 'Total time spent: 30 minutes.'
        for text, code, quote in (
                (B + 'Office visit note\n' + HEAD + 'Interpreter: Spanish, via phone.\nChief complaint\nHeartburn.\n' + EXAM
                 + 'Assessment and plan\nGERD. Continue omeprazole.\n' + time30 + '\n', '99213', time30),
                (office(cc='Heartburn. The visit was conducted with a telephonic Spanish interpreter.', plan='GERD.',
                        tail=time30 + '\n'), '99213', time30),
                (office(plan='GERD.', tail='Total time: 40 minutes, including a phone call with her daughter about her '
                                           'medications.\n'), '99214',
                 'Total time: 40 minutes, including a phone call with her daughter about her medications.'),
                (B + 'Office visit note\n' + HEAD + 'Reason for visit: reflux follow-up; she no-showed her colonoscopy in '
                 'August.\n' + EXAM + 'Assessment and plan\nGERD. Colonoscopy rescheduled.\n' + time30 + '\n', '99213',
                 time30),
                (B + 'Osprey Point Liver and Digestive Clinic (fictional)\nAfter-hours phone triage: 555-0103\nOffice visit '
                 'note\n' + HEAD + 'Chief complaint\nHeartburn.\n' + EXAM + 'Assessment and plan\nGERD.\n' + time30 + '\n',
                 '99213', time30),
                (B + 'Office visit note\n' + HEAD + 'Reason for visit: patient not seen in the office for two years; '
                 're-establishing care for reflux.\n' + EXAM + 'Assessment and plan\nGERD.\n' + time30 + '\n', '99213',
                 time30),
                (B + 'Office visit note\n' + HEAD + 'Visit note: scheduled as a telephone visit, converted to an in-person '
                 'visit at her request.\n' + EXAM + 'Assessment and plan\nGERD.\n' + time30 + '\n', '99213', time30),
                (office(cc='Heartburn. Allergies: none; confirmed by phone with her pharmacy.', tail=time30 + '\n'),
                 '99213', time30),
                (office(tail='Total time 30 minutes; I will call her with the biopsy results by phone.\n'), '99213',
                 'Total time 30 minutes'),
                (office(cc='Heartburn. Check-in: no-show policy reviewed with the patient.', tail=time30 + '\n'),
                 '99213', time30)):
            self.assertEqual(outcome(text, code, quote), READY, text)

    def test_only_a_statement_of_todays_encounter_type_holds(self):  # kills pv1-c4-today-mode
        self.assert_not_held(office(cc='Heartburn. Discussed management with Dr. Lee (cardiology) by phone.',
                                    tail='Total time: 30 minutes.\n'))

    def test_another_party_to_the_contact_holds_nothing(self):  # kills pv1-c4-third-party
        for words in ('Interpreter: Spanish interpreter via telephone, ID 4471.', 'Independent historian: her daughter, '
                                                                                   'by telephone.'):
            self.assert_not_held(office(cc=f'Heartburn. {words}', tail='Total time: 30 minutes.\n'))

    def test_another_time_holds_nothing(self):  # kills pv1-c4-other-time
        for words in ('Reason for visit: patient not seen in the office for two years.',
                      'She was not seen in the office for six months.'):
            self.assert_not_held(office(cc=f'Heartburn. {words}', tail='Total time: 30 minutes.\n'))

    def test_an_in_person_visit_stated_holds_nothing(self):  # kills pv1-c4-in-person
        self.assert_not_held(office(cc='Telephone visit converted to an in-person visit today.',
                                    tail='Total time: 30 minutes.\n'))
        # an in-person visit told of another time clears nothing
        for words in ('Spoke with the patient by phone; she was last seen in person in August.',
                      'Spoke with the patient by phone; seen in person in August.'):
            self.assert_c4_holds(office(exam='', cc=words, tail='Total time: 12 minutes.\n'))

    def test_a_contact_detail_holds_nothing(self):  # kills pv1-c4-contact-detail
        for line in ('After-hours phone triage: 555-0103', 'Preferred contact: by phone', 'Phone triage line 555-0103'):
            self.assert_not_held(B + f'Office visit note\n{line}\n' + HEAD + 'Chief complaint\nHeartburn.\n' + EXAM
                                 + 'Assessment and plan\nGERD.\nTotal time: 30 minutes.\n')
        # a number on the line of a contact with the patient clears nothing, nor does one beside a field naming today's
        # encounter
        for cc in ('Spoke with the patient by phone at 555-0199 about her results.',
                   'Telephone encounter: 555-0199 called back about her results.'):
            self.assert_c4_holds(office(exam='', cc=cc, tail='Total time: 12 minutes.\n'))

    def test_a_plan_or_a_preference_holds_nothing(self):  # kills pv1-c4-planned and pv1-c4-prefers
        for words in ('I will call her with the biopsy results by phone.', 'She prefers phone visits.'):
            self.assert_not_held(office(plan=f'GERD. {words}', tail='Total time: 30 minutes.\n'))

    def test_a_contact_under_a_heading_of_another_occasion_holds_nothing(self):  # kills pv1-c4-other-occasion
        text = office(tail='Total time spent: 30 minutes.\n\nAddendum 10/30/2026\nPathology discussed with the patient by '
                           'phone; H. pylori negative.\n')
        self.assertEqual(outcome(text, '99213', 'Total time spent: 30 minutes.'), READY)


class EMR7Tests(CycleCase):
    """EMR-7: the other-time holds held today's time whose activity list names the earlier event reviewed; an item that
    is today's work ON it (an activity noun leads it, no duration) is no other occasion of the minutes."""

    def test_the_lens_inputs_are_ready_as_installed(self):
        for line in ('Total time: 40 minutes, including review of the notes from her hospitalization in August.',
                     'Total time: 30 minutes, including counseling on the results discussed at her last visit.',
                     'Total time: 30 minutes, including comparison with the exam during her prior visit.',
                     'Total time: 32 minutes, including review of the findings at her prior visit.',
                     'Total time: 32 minutes, including discussion of labs drawn at her previous visit.'):
            self.assertEqual(facts(em(office(plan='GERD.', tail=line + '\n'))).get('time_minutes'),
                             line.split(': ')[1].split(' ')[0], line)

    def test_another_occasion_in_the_list_stays_held(self):  # kills pv1-c4time-item-duration
        for line in ('Total time: 40 minutes, including her visit in August.',
                     'Total time: 30 minutes, including 20 minutes at last visit.',
                     'Total time: 30 minutes, including review of records for 20 minutes at her last visit.',
                     'Total time: 30 minutes, including her prior visit.'):
            finding = em(office(tail=line + '\n'))
            self.assertNotIn('time_minutes', facts(finding), line)
            held = next(m for m in finding.mentions if m.span.text.startswith('Total time'))
            self.assertEqual((held.status, held.cues[0]), ('uncertain', detect.EM_ANOTHER_TIME), line)

    def test_a_reviewed_item_names_no_other_occasion(self):  # kills pv1-c4time-reviewed
        text = office(tail='Total time: 40 minutes, including review of the notes from her hospitalization in August.\n')
        self.assertEqual(facts(em(text)).get('time_minutes'), '40')
        self.assertTrue(detect._pv1_reviewed(text, text.index('including') + 9, text.index('in August')))

    def test_many_reviewed_items_route_in_bounded_time_and_hold(self):  # kills pv1-cost-item-bound
        # 2000 items, each today's review of "her recent visit" (read only by the prepositional words): past
        # _PV1_ITEM_MATCHES of them the statement is held (fail-closed), and the work per statement is bounded
        text = office(tail='Total time: 40 minutes, including ' + 'review of the results at her recent visit, ' * 2000
                      + 'and documentation.\n')
        jobs.release_routing_caches()
        started = time.process_time()
        finding = em(text)
        self.assertLess(time.process_time() - started, 10.0)
        self.assertNotIn('time_minutes', facts(finding))
        few = office(tail='Total time: 40 minutes, including ' + 'review of the results at her recent visit, ' * 3
                     + 'and documentation.\n')
        self.assertEqual(facts(em(few)).get('time_minutes'), '40')

    def test_many_unprepositioned_items_are_bounded_too(self):  # kills pv1-cost-unprepped-bound
        text = office(tail='Total time: 40 minutes, including ' + 'review of the results of her last visit, ' * 20
                      + 'and documentation.\n')
        self.assertNotIn('time_minutes', facts(em(text)))
        few = office(tail='Total time: 40 minutes, including ' + 'review of the results of her last visit, ' * 3
                     + 'and documentation.\n')
        self.assertEqual(facts(em(few)).get('time_minutes'), '40')


class EMR8Tests(CycleCase):
    """EMR-8 (a residual on both trees): telephone and no-show notes outside C4's old list were READY."""

    def test_the_lens_inputs_are_held_with_their_basis_documented(self):
        for text, quote, line in (
                (B + 'GI Clinic Note\n' + HEAD + 'Reviewed her labs.\nTotal time spent on phone with patient: 12 '
                 'minutes.\n', 'Total time spent on phone with patient: 12 minutes.',
                 'Total time spent on phone with patient: 12 minutes.'),
                (B + 'GI Clinic Note\n' + HEAD + 'Reviewed her labs.\nTotal time: 12 minutes (telephone).\n',
                 'Total time: 12 minutes', 'Total time: 12 minutes (telephone).'),
                (B + 'GI Clinic Note\nEncounter: Telephone\n' + HEAD + 'Reviewed her labs.\nTotal time: 12 minutes.\n',
                 'Total time: 12 minutes.', 'Encounter: Telephone'),
                (B + 'GI Clinic Note\n' + HEAD + 'The patient did not come in today; appointment to be rebooked.\n'
                 'Total time: 15 minutes.\n', 'Total time: 15 minutes.',
                 'The patient did not come in today; appointment to be rebooked.')):
            self.assert_c4_holds(text, line)
            self.assertEqual(outcome(text, '99212', quote), ('selected', 'needs_clarification', ('performed_status',)),
                             text)

    def test_a_plan_sentence_is_read(self):  # kills pv1-c4-plan-read
        text = B + ('GI Clinic Note\n' + HEAD + 'Assessment and plan\nReviewed the biopsy results with the patient by '
                    'telephone.\nH. pylori gastritis; quadruple therapy sent.\nTotal time: 12 minutes.\n')
        self.assertEqual(detect.layout(text).section_at(text.index('by telephone')).kind, 'plan')
        self.assert_c4_holds(text, 'Reviewed the biopsy results with the patient by telephone.')

    def test_a_head_title_naming_a_telephone_note_holds(self):  # kills pv1-c4-head
        # "Telephone note" is read by the statement scan as a data item ("telephone notes reviewed"); as a title of the
        # note's head it names today's encounter
        text = B + 'Telephone note\n' + HEAD + 'Reviewed her labs with her.\nTotal time: 12 minutes.\n'
        self.assert_c4_holds(text, 'Telephone note')

    def test_a_history_clause_that_says_today_is_read(self):
        text = B + ('GI Clinic Note\n' + HEAD + 'History of present illness\nContacted by telephone today regarding her '
                    'biopsy results.\nAssessment and plan\nGERD.\nTotal time: 12 minutes.\n')
        self.assert_c4_holds(text, 'Contacted by telephone today regarding her biopsy results.')

    def test_the_statements_own_sentence_holds_the_document(self):  # kills pv1-c4-own-sentence
        text = B + ('GI Clinic Note\n' + HEAD + 'History of present illness\nI spent 15 minutes by telephone with the '
                    'patient.\nAssessment and plan\nGERD.\n')
        self.assertEqual(detect.layout(text).section_at(text.index('by telephone')).kind, 'history')
        finding = self.assert_c4_holds(text, 'I spent 15 minutes by telephone with the patient.')
        self.assertEqual(facts(finding).get('time_minutes'), '15')  # CTS-2: today's statement is its basis


class EMR9Tests(CycleCase):
    """EMR-9 (a residual on both trees): another visit's time or level, and 'shared decision making', gave a basis."""

    def test_the_lens_inputs_are_held(self):
        for text, code, quote in (
                (office(plan='GERD.', tail='Total time last visit: 40 minutes.\n'), '99214', 'Total time last visit: 40 '
                                                                                             'minutes.'),
                (office(plan='GERD.', tail='Total time: 45 minutes (today 25, previous visit 20).\n'), '99214',
                 'Total time: 45 minutes'),
                (office(plan='GERD.', tail='MDM at her last visit: high.\n'), '99215', 'MDM at her last visit: high.'),
                (office(plan='GERD.', tail='Shared medical decision making regarding screening, risk level moderate.\n'),
                 '99214', 'Shared medical decision making regarding screening, risk level moderate.')):
            bucket, status, clarifications = outcome(text, code, quote)
            self.assertEqual((bucket, status), ('selected', 'needs_clarification'), text)
            finding = em(text)
            self.assertFalse({'time_minutes', 'mdm_level', 'em_basis'} & set(facts(finding)), text)

    def test_another_visit_without_a_preposition_holds_a_time(self):  # kills pv1-emr9-unprepped
        finding = em(office(tail='Total time last visit: 40 minutes.\n'))
        self.assertNotIn('time_minutes', facts(finding))

    def test_a_parenthesis_after_the_minutes_is_read(self):  # kills pv1-emr9-paren
        finding = em(office(tail='Total time: 45 minutes (today 25, previous visit 20).\n'))
        self.assertNotIn('time_minutes', facts(finding))
        # a parenthesis naming no other visit holds nothing
        self.assertEqual(facts(em(office(tail='Total time: 45 minutes (face to face 30).\n'))).get('time_minutes'), '45')

    def test_installeds_mdm_reading_takes_the_other_visit_hold(self):  # kills pv1-emr9-mdm-other-visit
        self.assertNotIn('mdm_level', facts(em(office(tail='MDM at her last visit: high.\n'))))
        self.assertEqual(facts(em(office(tail='MDM: high.\n'))).get('mdm_level'), 'high')

    def test_decision_making_statements_take_the_other_time_holds(self):  # kills pv1-c2-another-time
        self.assertNotIn('mdm_level', facts(em(office(tail='Medical decision making during her prior visit: high.\n'))))

    def test_a_level_after_shared_is_held(self):  # kills pv1-emr9-shared
        finding = em(office(tail='Shared medical decision making regarding screening, risk level moderate.\n'))
        self.assertNotIn('mdm_level', facts(finding))
        held = next(m for m in finding.mentions if m.span.text.startswith('medical decision making'))
        self.assertEqual(held.cues, (detect._PV1_SHARED,))

    def test_known_limit_an_addendum_dated_time_reads_as_installed(self):
        # arguable (the judge), recorded in the declaration's known limits: no rule here reads it
        text = office(tail='\nAddendum 10/30/2026\nTotal time spent: 20 minutes reviewing the outside pathology.\n')
        self.assertEqual(facts(em(text)).get('time_minutes'), '20')


CTS1_BASE = B + 'Office visit note\n' + HEAD + 'Chief complaint\nHeartburn.\n' + EXAM


class CTS1Tests(CycleCase):
    """CTS-1: C4 and C4-time held eleven correct in-person office visits READY on installed."""

    def test_the_eleven_variants_are_ready(self):
        mdm = 'Medical decision making: moderate.'
        plan = 'Assessment and plan\nGERD. Continue omeprazole.\n'
        variants = (
            (CTS1_BASE + mdm + ' Discussed management with Dr. Lee (cardiology) by phone.\n' + plan, mdm),
            (B + 'Office visit note\n' + HEAD + 'Interpreter: Spanish interpreter via telephone, ID 4471.\nChief complaint\n'
             'Heartburn.\n' + EXAM + mdm + '\n' + plan, mdm),
            (CTS1_BASE.replace('Heartburn.', 'Heartburn; she missed her appointment in August and is seen today.')
             + mdm + '\n' + plan, mdm),
            (CTS1_BASE.replace('Heartburn.', 'Heartburn. She was a no-show for her EGD in September.') + mdm + '\n' + plan,
             mdm),
            (CTS1_BASE + 'Independent historian: her daughter, by telephone.\n' + mdm + '\n' + plan, mdm),
            (CTS1_BASE + 'Data reviewed: telephone notes from the nurse line.\n' + mdm + '\n' + plan, mdm),
            (CTS1_BASE + plan + 'Total time: 32 minutes, including 10 minutes on the phone with her cardiologist.\n',
             'Total time: 32 minutes, including 10 minutes on the phone with her cardiologist.'),
            (B + 'Office visit note\n' + HEAD + 'Interpreter: Spanish, via phone.\nChief complaint\nHeartburn.\n' + EXAM
             + plan + 'Total time: 32 minutes.\n', 'Total time: 32 minutes.'),
            (B + 'Office visit note\n' + HEAD + 'Chief complaint\nHeartburn.\nPhysical exam\nShe called by phone yesterday; '
             'seen in person today. Abdomen soft.\n' + mdm + '\n' + plan, mdm),
            (CTS1_BASE + plan + 'Total time: 32 minutes, including review of the findings at her prior visit.\n',
             'Total time: 32 minutes, including review of the findings at her prior visit.'),
            (CTS1_BASE + plan + 'Total time: 32 minutes, including discussion of labs drawn at her previous visit.\n',
             'Total time: 32 minutes, including discussion of labs drawn at her previous visit.'))
        for text, quote in variants:
            self.assertEqual(outcome(text, '99214', quote), READY, text)


TELEPHONE_TIME = B + ('Telephone encounter\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\n'
                      'Established patient\nThe patient was not seen in the office; we spoke by telephone about her '
                      'reflux.\nTotal time: 15 minutes.\n')


class CTS2Tests(CycleCase):
    """CTS-2: every C4 hold also said the visit-level basis was undocumented beside a reason quoting the very MDM or
    time statement, and the cue quoted a 2-3 word fragment of its line."""

    def test_a_held_document_states_its_basis(self):  # kills pv1-cts2-basis
        bucket, status, clarifications, checks = assess(TELEPHONE_TIME, '99212', 'Total time: 15 minutes.')
        self.assertEqual((bucket, status, sorted(clarifications)), ('selected', 'needs_clarification',
                                                                   ['performed_status']))
        self.assertNotIn('em_basis', clarifications)
        self.assertNotIn('Not documented: basis', ' '.join(detail for _, detail in checks.values()))
        self.assertIn('Total time: 15 minutes.', clarifications['performed_status'])
        self.assertIn(f"{detect.EM_NOT_IN_PERSON}: 'Telephone encounter'", clarifications['performed_status'])
        got = facts(em(TELEPHONE_TIME))
        self.assertEqual((got.get('em_basis'), got.get('time_minutes')), ('time', '15'))

    def test_the_in_person_variants_raise_no_question(self):
        text = CTS1_BASE + ('Medical decision making: moderate. Discussed management with Dr. Lee (cardiology) by '
                            'phone.\nAssessment and plan\nGERD. Continue omeprazole.\n')
        _, _, clarifications, _ = assess(text, '99214', 'Medical decision making: moderate.')
        self.assertEqual(clarifications, {})

    def test_a_statement_held_as_another_visits_is_no_basis_of_today(self):
        text = TELEPHONE_TIME.replace('Total time: 15 minutes.', 'Total time at her last visit was 40 minutes.')
        self.assertNotIn('em_basis', facts(em(text)))

    def test_the_cue_quotes_the_line(self):
        # the whole line, so a reader sees what else it says, never the two words matched
        text = office(exam='', cc='Heartburn. She was reached by telephone about her reflux.',
                      tail='Total time: 12 minutes.\n')
        self.assert_c4_holds(text, 'Heartburn. She was reached by telephone about her reflux.')

    def test_a_long_line_is_quoted_around_its_words(self):  # kills pv1-line-quote
        words = 'Spoke with the patient by telephone.'
        line = 'Words before. ' * 20 + words + ' Words after.' * 20
        text = office(exam='', cc=line, tail='Total time: 12 minutes.\n')
        finding = self.assert_c4_holds(text)
        quote = finding.mentions[0].cues[0][len(detect.EM_NOT_IN_PERSON) + 3:-1]
        self.assertLessEqual(len(quote), detect._PV1_LINE_QUOTE + 2)
        self.assertTrue(quote.startswith('…') and quote.endswith('…'), quote)
        self.assertIn('by telephone', quote)


# --- the visit evidence the releases need -----------------------------------------------------------------------------

class VisitEvidenceTests(CycleCase):
    """_pv1_office_visit: positive evidence of today's in-person office visit, read once per document."""

    def evidence(self, text):
        return detect._pv1_office_visit(detect._analysis(text, DAY)[0])

    def test_an_office_note_with_an_exam(self):
        self.assertIsNone(self.evidence(office()))
        self.assertIsNone(self.evidence(office(exam='Vital Signs and Exam\nWeight 61.4 kg, blood pressure 112/70.\n')))
        self.assertIsNone(self.evidence(office(exam='Exam: abdomen soft, nontender.\n')))

    def test_no_exam_content_is_no_evidence(self):  # kills pv1-visit-exam
        for exam in ('', 'Physical exam\nDeferred.\n', 'Exam: 10/01\n', 'Objective\nCT abdomen 10/01/2026: 3 cm liver '
                                                                          'mass.\n', 'Physical exam\nNot performed.\n'):
            self.assertEqual(self.evidence(office(exam=exam)), 'no exam or vital signs are recorded', exam)
        text = office(exam='', tail='Complexity of decision making: moderate.\n')
        self.assert_label_not_read(text, 'Complexity of decision making: moderate')

    def test_reported_values_are_no_exam(self):  # kills pv1-visit-reported
        for exam in ('Vitals: patient-reported weight 150 lb\n', 'Physical exam: abdomen soft (per last visit)\n',
                     'Vital signs: home blood pressure 130/80\n'):
            self.assertEqual(self.evidence(office(exam=exam)), 'no exam or vital signs are recorded', exam)
        text = office(title='GI Clinic Note', exam='Vitals: patient-reported weight 150 lb\n',
                      tail='Complexity of decision making: low.\n')
        self.assert_label_not_read(text, 'Complexity of decision making: low')

    def test_no_office_setting_is_no_evidence(self):  # kills pv1-visit-setting
        text = office(head='Date of service: 10/26/2026\nPlace of service: inpatient hospital (POS 21)\nEstablished '
                           'patient\n', tail='Complexity of decision making: low.\n')
        self.assertEqual(self.evidence(text), 'no office setting is documented')
        self.assert_label_not_read(text, 'Complexity of decision making: low')

    def test_not_a_visit_words(self):
        for words in ('E-visit.', 'Online visit questionnaire reviewed.', 'B12 injection visit.', 'RN visit.',
                      'Patient portal message.', 'She cancelled.'):
            self.assertIsNotNone(self.evidence(office(cc=f'Heartburn. {words}')), words)
        # a plan clause carrying a planned cue speaks of a future contact; a history clause not saying today, of the past
        self.assertIsNone(self.evidence(office(plan='GERD. Telephone follow-up in two weeks.')))
        self.assertIsNone(self.evidence(B + 'Office visit note\n' + HEAD + 'History of present illness\nShe called last '
                                        'week to report heartburn.\n' + EXAM + 'Assessment and plan\nGERD.\n'))

    def test_h4_01_documents_its_office_visit(self):
        from ops.gi4 import regression
        text = regression.load_fixtures()['h4-01']['text']
        an = detect._analysis(text, DAY)[0]
        self.assertIsNone(detect._pv1_office_visit(an))
        statements = [m for m in an.em if m.kind in ('em-time', 'em-mdm')]
        self.assertEqual(len(statements), 2)
        self.assertEqual([detect._pv1_statement_refused(an, m) for m in statements], [None, None])
