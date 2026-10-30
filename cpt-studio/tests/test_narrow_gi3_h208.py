"""CPT Studio GI round 3, the narrow release (the owner's decision of 2026-10-30): h2-08's charge block.

The installed reading skips every date label a plan or history section holds, so h2-08's charge block - "Charge
information" / "Date of service: 2026-10-06" at the end of its "Assessment and plan" - was dropped and the header's
contradicted "Date of service: 2026-10-05" was sent. Now, where the installed reading sends a date, a date of service in
the note's own closing charge block (the closed class context.CHARGE_HEADINGS; never a visit or procedure date, never a
history section's block) that states another date makes the date a question, and no date is sent. The question keeps
the document's own evidence only: a member's answer is taken only when it is the document's own date, the one the
installed revision sends, and the block's date is named only as the block's (context.CHARGE_DATE_NOTE,
charge_date_problem) - the block may record another occurrence. Every other fact reads exactly as the installed revision
90377ec6f413 read it, its texts and the answers it takes included: with no own date the charge block's date stays
dropped, and where it already asks, nothing changes. Synthetic text only.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context
from studio.providers.corti import build_coding_request
from studio.validation import checks

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3'
H208 = (FIXTURES / 'live-text' / 'h2-08__e084b793__2026-10-29.txt').read_text(encoding='utf-8')
STRANGER = '2026-10-01'  # a date no text here documents
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
HEADER = (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nPatient: Synthetic Patient (fictional)\n'
          'Date of service: 2026-10-05\nPlace of service: office (POS 11)\nEstablished patient\n\nSubjective\n'
          'Follow-up of anemia.\n\n')
UNDATED = HEADER.replace('Date of service: 2026-10-05\n', '')
PLAN = 'Assessment and plan\nContinue iron. Return in 3 months.\n'


def date_fact(text):
    return context.extract_context(text)['service_date']


def date_lines(text):
    request = build_coding_request('corti', 'test', text, context.service_date_of(text), 10 ** 7)
    return list(request.contexts[1:])


def merged(text, value):
    return context.merge_user_values(context.extract_context(text), {'service_date': value})['service_date']


def member(text, value):
    return 'held' if context.is_member_conflict(merged(text, value)) else 'taken'


def quoted_dates(note):
    """The calendar dates the quotes in a text state (ISO strings)."""
    return {day.isoformat() for quote in re.findall('\u201c([^\u201d]*)\u201d', note)
            for day in (context.date_from_match(m) for m in context.FULL_DATE.finditer(quote)) if day}


def reason_of(text):
    state = checks.service_date_state(context.extract_context(text), None)
    clarification = checks.service_date_clarification(state)
    return clarification.reason if clarification else None


class ChargeBlockTests(SimpleTestCase):
    def assert_asked(self, text, charge='2026-10-06', own='2026-10-05'):
        """The narrow release: the date is asked and no date is sent. The question names the block's date as the block's
        and the document's own as its own; its evidence is the document's own only, so the document's own date is a
        member's answer and the block's never is - nor is it quoted as "the document gives" in a held answer's note."""
        fact = date_fact(text)
        problem = context.charge_date_problem(fact)
        self.assertEqual(fact.origin, 'conflict', [e.text for e in fact.evidence])
        self.assertIsNotNone(problem, fact.note)
        self.assertEqual({d for e in fact.evidence for d in quoted_dates('\u201c' + e.text + '\u201d')}, {own})
        self.assertEqual(context.documented_values(fact), ())  # no value a member's answer may choose
        self.assertEqual(date_lines(text), [])  # no date is sent
        self.assertTrue(problem.startswith('The charge or billing block that ends the document states \u201c'), problem)
        self.assertIn(charge, {d for d in quoted_dates(problem.split("other than the document's own", 1)[0])})
        self.assertEqual(quoted_dates(problem.split("other than the document's own", 1)[1]), {own})
        self.assertEqual(reason_of(text), problem + '; every service and every dated reference check depends on it.')
        self.assertEqual(context.charge_date_own(fact), own)
        self.assertEqual(member(text, own), 'taken')
        for value in (charge, STRANGER):  # held with the installed note: the document gives its own date
            self.assertEqual(merged(text, value).note, context.USER_CONFLICT_NOTE.format(user=value, document=own), value)

    def assert_never_answered(self, text, other, own='2026-10-05'):
        """Another occurrence's date in a closing charge block the guards may miss: asked or read as installed, never
        sent and never a member's answer (the narrow release's second refutation)."""
        self.assertIn(date_lines(text), ([], [f'Date of service: {own}']))
        self.assertEqual(member(text, other), 'held')
        self.assertEqual(member(text, own), 'taken')
        self.assertLessEqual(quoted_dates(merged(text, other).note), {own})
        problem = context.charge_date_problem(date_fact(text))
        if problem is not None:  # asked: the other date is named as the block's only
            self.assertEqual(quoted_dates(problem.split("other than the document's own", 1)[1]), {own})

    def assert_installed(self, text, value='2026-10-05'):
        """As the installed revision reads it: the header's own date, sent; a different member date held."""
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('document', value), [e.text for e in fact.evidence])
        self.assertEqual(date_lines(text), [f'Date of service: {value}'])
        self.assertEqual(member(text, STRANGER), 'held')

    def test_h2_08_is_asked_and_no_date_is_sent(self):
        self.assert_asked(H208)

    def test_charge_and_billing_blocks_speak_against_the_notes_own_date(self):
        for block in ('Charge information\nDate of service: 2026-10-06\n',
                      'Charges\nDOS: 10/06/2026\n',
                      '5. Charge information\nDate of service: 2026-10-06\n',
                      'Charge information: Date of service: 2026-10-06\n',
                      'Billing & coding\nCPT: 99214\nDate of service: 2026-10-06\n',
                      '## Coding\nEncounter date: 2026-10-06\n',
                      'Charge information\n\nDate of service: 2026-10-06\n',  # a blank line inside the closing block
                      # the narrow refutation's dates-n1: a code, a cell row or a bold heading inside the block
                      'Charge information\nCPT 99214\nDate of service: 2026-10-06\nDiagnosis: anemia\n',
                      'Charge information\nCPT | Description | Units\n99214 | Office visit, established patient | 1\n'
                      'Date of service: 2026-10-06\n',
                      '**Charge information**\nDate of service: 2026-10-06\n',
                      'Charge information\nDate of service: 2026-10-06\n\n'
                      'Electronically signed: Synthetic Doctor, MD (fictional), 2026-10-06 09:12\n',
                      'Charge information\nDate of service: 2026-10-06\nSigned by Synthetic Doctor, MD (fictional)\n',
                      # the second refutation's dates-n2-8: the heading joined to its first field by a dash
                      'Charge Information — Date of Service: 2026-10-06\nDiagnosis: anemia\n',
                      'Charge Information – Date of Service: 2026-10-06\nDiagnosis: anemia\n',
                      'CHARGE INFORMATION - Date of Service: 2026-10-06\nDiagnosis: anemia\n',
                      # the fourth refutation's dates-n4-3: an underscore bold heading, a dash with no blanks
                      '__Charge information__\nDate of service: 2026-10-06\n',
                      '__Charges:__\nDate of service: 2026-10-06\n',
                      'Charge information—Date of service: 2026-10-06\nDiagnosis: anemia\n',
                      'Charge Information–Date of Service: 2026-10-06\nDiagnosis: anemia\n'):
            with self.subTest(block=block):
                self.assert_asked(HEADER + PLAN + block)

    def test_a_block_installed_reads_in_a_section_of_its_own_stays_installeds_conflict(self):
        # "BILLING INFORMATION:" and "Diagnosis:" open sections of their own, outside the plan: the installed reading
        # already reads the date there as a second own date, a conflict either date answers. The release leaves it so.
        for block in ('BILLING INFORMATION:\nService date: 2026-10-06\n',
                      'Superbill\nDiagnosis: anemia\nDate of encounter: 2026-10-06\n'):
            with self.subTest(block=block):
                text = HEADER + PLAN + block
                fact = date_fact(text)
                self.assertEqual((fact.origin, context.documented_values(fact)), ('conflict', ('2026-10-05', '2026-10-06')))
                self.assertEqual((member(text, '2026-10-05'), member(text, '2026-10-06')), ('taken', 'taken'))

    def test_controls_every_other_block_reads_as_installed(self):
        for block in ('Next appointment\nDate of service: 2026-11-18\n',
                      'Pathology\nDate of service: 2026-10-06\n',
                      'Labs\nDate of service: 2026-10-06\n',
                      'Prior visit charges\nDate of service: 2026-09-01\n',
                      'Charges for the next visit\nDate of service: 2026-11-18\n',
                      'Charge information\nOffice visit, established patient\nDate of service: 2026-10-06\n',
                      'Charge information\nVisit date: 2026-10-06\n',  # a visit date: a plan may book it
                      'Charge information\nProcedure date: 2026-10-06\n',
                      'Charge information\nNext date of service: 2026-11-18\n',  # its own words: another occurrence
                      # ... in words no guard holds, which the label's own reader places in another occurrence
                      'Charge information\nRepeat date of service: 2026-09-01\n',
                      'Charge information\nProposed date of service: 2026-11-18\n',
                      # a line longer than CHARGE_HEADING_REACH is never read (a cost bound), so its block reads as
                      # installed
                      'Charge information\nDate of service: 2026-10-06\nComment: ' + 'reviewed with the patient ' * 5
                      + '\n'):
            with self.subTest(block=block):
                self.assert_installed(HEADER + PLAN + block)

    def test_controls_a_charge_block_of_another_occurrence_reads_as_installed(self):
        """The narrow refutation's dates-n3 and dates-n4: a charge or billing block that is not the note's own closing
        charge block - a copied report's in the middle of the note, a booking, a prior visit's late charge, a date of
        birth auto-filled into its field - is never offered as an answer: it reads as installed."""
        for block in (
                'Charge information\nDate of service: 2026-04-02\nCPT: 45385\nToday\'s visit\nDoing well.\n',
                'Billing information\nColonoscopy scheduled at Synthetic Endoscopy Center.\nPrior authorization: '
                'submitted\nDate of service: 2026-11-04\n',
                'Billing\nCPT: 45378\nDate of service: 2026-11-04\nScheduled procedure; prior authorization pending.\n',
                'Charges\nLate charge for the previous visit, which was not entered at the time.\nCPT: 99213\n'
                'Date of service: 2026-09-28\n',
                'Charges\nPathology: specimen read\nDate of service: 2026-10-08\n'):
            with self.subTest(block=block):
                self.assert_installed(HEADER + PLAN + block)
        # a copied charge block in the middle of the plan, beside the note's own closing one: only the closing block speaks
        copied = (HEADER + PLAN + 'Charges\nDate of service: 2026-04-02\nCPT: 45385\nThe copied note ends here.\n'
                  'Assessment and plan\nStable.\nCharge information\nDate of service: 2026-10-05\n')
        self.assert_installed(copied)
        # a copied note at the end, with its own plan and charge block (the refutation's f1b), or its title inside the plan
        for note in ('Previous visit note (copied for reference)\nAssessment and plan\nStart iron.\n'
                     'Charge information\nDate of service: 2026-09-01\nDiagnosis: anemia\n',
                     'Previous visit note (copied for reference)\nCharge information\nDate of service: 2026-09-01\n',
                     # its title further up, over its own date and history (read back to the first plan section)
                     'Previous visit note (copied for reference)\nDate of service: 2026-09-01\nHPI\n'
                     'Anemia follow-up.\n\nAssessment and plan\nStart iron.\nCharge information\n'
                     'Date of service: 2026-09-01\nDiagnosis: anemia\n'):
            with self.subTest(note=note):
                self.assert_installed(HEADER + PLAN + '\n' + note)
        # the note's own part with no plan section, then a copied note: its title stands right above its plan, the
        # document's first plan section (the nearest non-empty line above the reach is read)
        self.assert_installed(HEADER + 'Objective\nAbdomen soft.\n\nPrevious visit note (copied for reference)\n'
                              'Assessment and plan\nStart iron.\nCharge information\nDate of service: 2026-09-01\n')
        with_birth = HEADER.replace('Patient: Synthetic Patient (fictional)\n',
                                    'Patient: Synthetic Patient (fictional)\nDate of birth: 1959-06-02\n')
        text = with_birth + PLAN + 'Charge information\nVisit type: Follow-up\nDate of service: 06/02/1959\n'
        self.assert_installed(text)
        self.assertEqual(member(text, '1959-06-02'), 'held')

    def test_a_history_heading_above_the_plan_leaves_the_closing_block_speaking(self):
        # a copied note's title is read back to the document's first plan section only: the note's own history above
        # its plan ("Prior procedures", "Previous colonoscopy") is no copied note's title
        for history in ('Prior procedures\nColonoscopy in 2023.\n\n',
                        'Previous colonoscopy\nTwo small polyps removed.\n\n'):
            with self.subTest(history=history):
                self.assert_asked(HEADER + history + PLAN + 'Charge information\nDate of service: 2026-10-06\n')

    def test_a_plan_sentence_naming_another_occurrence_leaves_the_closing_block_speaking(self):
        # only a heading-like line is read for a copied note's title: a plan's own sentences name later occurrences
        plan = 'Assessment and plan\nRepeat colonoscopy is scheduled for next year.\nPathology is pending.\n'
        self.assert_asked(HEADER + plan + 'Charge information\nDate of service: 2026-10-06\n')

    def test_another_occurrences_block_the_guards_miss_is_never_answered_or_sent(self):
        """The second refutation's dates-n2-1 to n2-7: closing charge blocks of another occurrence that pass the guards.
        Each is asked at most - its date quoted, never a member's answer, never sent."""
        signed = 'Electronically signed: Synthetic Doctor, MD (fictional), 2026-10-05 17:02\n'
        cases = (
            # a copied note announced in a sentence, with its own date, plan and charge block
            ('2026-09-01', PLAN + signed + '\nThe previous visit note is copied below for reference.\n'
             'Date of service: 2026-09-01\nAssessment and plan\nStart iron.\nCharge information\n'
             'Date of service: 2026-09-01\nDiagnosis: anemia\n'),
            # a date of birth written in a form the reader does not read, auto-filled into the charge date
            ('1959-06-02', PLAN + 'Charge information\nDate of service: 06/02/1959\nDiagnosis: anemia\n'),
            # a booking announced in a sentence before a billing block
            ('2026-11-04', 'Assessment and plan\nUpper endoscopy is booked at Synthetic Endoscopy Center (fictional) for '
             '11/04/2026.\nBilling\nDate of service: 11/04/2026\nCPT: 43235\n'),
            # another patient's charge block pasted at the end
            ('2026-08-14', PLAN + 'Charges\nPatient: Another Synthetic Patient (fictional)\nDate of service: 2026-08-14\n'
             'CPT: 99213\n'),
        )
        for other, tail in cases:
            with self.subTest(other=other):
                header = HEADER.replace('Patient: Synthetic Patient (fictional)\n',
                                        'Patient: Synthetic Patient (fictional)\nDOB: 06/02/59\n')
                self.assert_never_answered(header + tail, other)

    def test_where_the_installed_reading_already_asks_nothing_changes(self):
        """The third refutation's dates-n3-2, n3-3 and STATE3N-W1: the release changes only a fact the installed reading
        sends. Where the document's own dates already make it ask - an own date in a form it does not read, a title or a
        second label stating another day, a title stating the block's day - the fact is exactly the installed reading's,
        its question and the answers it takes included: the block's date is never quoted as a documented one."""
        block = 'Charge information\nDate of service: 2026-10-06\nDiagnosis: anemia\n'
        for header in (HEADER.replace('Clinic note\n', 'Clinic note\nDOS: 10/5/26\n'),
                       HEADER.replace('Clinic note\n', 'Hepatology clinic visit - 10/04/2026\n'),
                       HEADER.replace('Established patient\n', 'Established patient\nEncounter date: 2026-10-04\n'),
                       HEADER.replace('Clinic note\n', 'Hepatology clinic visit - 10/06/2026\n')):
            with self.subTest(header=header[len(BANNER):][:80]):
                text, without = header + PLAN + block, header + PLAN
                fact, installed = date_fact(text), date_fact(without)
                self.assertNotEqual(installed.origin, 'document')
                self.assertEqual(fact, installed)
                self.assertEqual(reason_of(text), reason_of(without))
                self.assertNotIn('Date of service: 2026-10-06', reason_of(text))
                for value in ('2026-10-04', '2026-10-05', '2026-10-06', STRANGER):
                    self.assertEqual(member(text, value), member(without, value), value)

    def test_a_members_other_date_is_held_quoting_the_documents_own_date_only(self):
        # the third refutation's dates-n3-1: a member's typo is held, and its note names only the document's own date as
        # what "the document gives" - never the block's
        for text in (H208, HEADER + PLAN + 'Charges\nPatient: Another Synthetic Patient (fictional)\n'
                                          'Date of service: 2026-10-06\nCPT: 99213\n'):
            with self.subTest(text=text[-60:]):
                self.assertEqual(merged(text, '2026-10-15').note,
                                 context.USER_CONFLICT_NOTE.format(user='2026-10-15', document='2026-10-05'))

    def test_a_hyphen_joined_own_date_is_still_the_answer_it_takes(self):
        """The fourth refutation's dates-n4-1: the installed reading reads and sends a date hyphen-joined to its label
        ("DOS-10/05/2026"), which a re-read of the evidence does not read. The question its charge block asks takes and
        holds a member's date exactly as that sent fact does: the document's own date taken, any other held."""
        for own_line in ('DOS-10/05/2026', 'Date of Service-10/05/2026', 'Date of service -2026-10-05'):
            with self.subTest(own_line=own_line):
                text = (HEADER.replace('Date of service: 2026-10-05', own_line) + PLAN
                        + 'Charge information\nDate of service: 2026-10-06\n')
                fact = date_fact(text)
                self.assertEqual((fact.origin, context.charge_date_own(fact)), ('conflict', '2026-10-05'))
                self.assertEqual(date_lines(text), [])
                self.assertEqual((merged(text, '2026-10-05').origin, merged(text, '2026-10-05').value), ('user', '2026-10-05'))
                self.assertEqual(merged(text, '2026-10-06').note,
                                 context.USER_CONFLICT_NOTE.format(user='2026-10-06', document='2026-10-05'))

    def test_a_block_that_states_the_documents_own_date_or_an_entry_after_the_signature_asks_nothing(self):
        """The fourth refutation's dates-n4-2: the block ends at its first signature line, and a block that states the
        document's own date does not contradict it - a later entry's date (a telephone call, an appointment, a lab draw)
        is never named as the block's."""
        signed = 'Electronically signed: Synthetic Doctor, MD (fictional), 2026-10-05 17:02\n'
        for tail in ('Charge information\nDate of service: 2026-10-05\nCPT: 99214\n' + signed
                     + 'Telephone encounter (DOS: 10/07/2026): labs reviewed with the patient. No charge.\n',
                     'Charge information\nDate of service: 2026-10-05\nCPT: 99214\n' + signed
                     + 'Telephone call: labs reviewed, no charge\nDate of service: 2026-10-07\n',
                     'Charge information\nDate of service: 2026-10-05\nDate of service: 2026-10-06\nCPT: 99214\n'):
            with self.subTest(tail=tail[-50:]):
                self.assert_installed(HEADER + PLAN + tail)
        # the block's own date still asks, and only it is named
        text = (HEADER + PLAN + 'Charge information\nDate of service: 2026-10-06\n' + signed
                + 'Follow-up appointment: DOS 11/04/2026 at 09:00 with Synthetic Doctor (fictional).\n')
        self.assert_asked(text)
        problem = context.charge_date_problem(date_fact(text))
        self.assertEqual(quoted_dates(problem.split("other than the document's own", 1)[0]), {'2026-10-06'})

    def test_an_equal_date_changes_nothing(self):
        self.assert_installed(HEADER + PLAN + 'Charge information\nDate of service: 2026-10-05\n')

    def test_with_no_own_date_nothing_is_newly_sent(self):
        text = UNDATED + PLAN + 'Charge information\nDate of service: 2026-10-06\n'
        self.assertEqual(date_fact(text).origin, 'missing')
        self.assertEqual(date_lines(text), [])
        self.assertEqual(member(text, STRANGER), 'taken')  # as installed: the label stays dropped

    def test_a_history_sections_charge_block_reads_as_installed(self):
        # a history section's charge block may bill a prior occurrence: asking would offer its date as an answer
        for history in ('Interval history\nDoing well.\n', 'Prior procedures:\nColonoscopy in 2023.\n'):
            with self.subTest(history=history):
                text = (HEADER.replace('Subjective\nFollow-up of anemia.\n\n', '') + history
                        + 'Billing\nDate of service: 2026-10-06\n')
                self.assert_installed(text)

    def test_the_heading_reader(self):
        for line in ('Charge information', 'CHARGE INFORMATION:', '5. Charges', '## Billing & coding', '- Superbill -'):
            with self.subTest(line=line):
                self.assertIn(context._heading_words(line), context.CHARGE_HEADINGS)
        for line in ('Prior visit charges', 'Next appointment', 'Charge information for the next visit', 'Billing note'):
            with self.subTest(line=line):
                self.assertNotIn(context._heading_words(line), context.CHARGE_HEADINGS)
