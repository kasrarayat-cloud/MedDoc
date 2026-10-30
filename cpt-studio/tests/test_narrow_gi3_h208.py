"""CPT Studio GI round 3, the narrow release (the owner's decision of 2026-10-30): h2-08's charge block.

The installed reading skips every date label a plan or history section holds, so h2-08's charge block - "Charge
information" / "Date of service: 2026-10-06" at the end of its "Assessment and plan" - was dropped and the header's
contradicted "Date of service: 2026-10-05" was sent. Now a date of service in the note's own closing charge block (the
closed class context.CHARGE_HEADINGS; never a visit or procedure date, never a history section's block) speaks against
the note's own labelled date: where they differ the date is asked, and no date is sent. The block may record another
occurrence, so its date is quoted but never a member's answer (context.CHARGE_DATE_NOTE, USER_CHARGE_NOTE); only the
document's own date, which the installed revision sends, is taken. Everything else reads as the installed revision
90377ec6f413 read it: with no own date the charge block's date stays dropped, so nothing is ever newly sent. Synthetic
text only.
"""
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


class ChargeBlockTests(SimpleTestCase):
    def assert_asked(self, text, charge='2026-10-06', own='2026-10-05'):
        """The narrow release: the date is asked, no date is sent and the question quotes both lines as the block's and
        the document's own; the document's own date is a member's answer, the charge block's never is."""
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.note), ('conflict', context.CHARGE_DATE_NOTE), [e.text for e in fact.evidence])
        self.assertEqual(context.documented_values(fact), ())  # no value a member's answer may choose from the block
        self.assertEqual(date_lines(text), [])  # no date is sent
        reason = checks.service_date_clarification(checks.service_date_state(context.extract_context(text), None)).reason
        self.assertTrue(reason.startswith('The charge or billing block that ends the document states a date of service '
                                          "other than the document's own ("), reason)
        self.assertEqual(member(text, own), 'taken')
        self.assertEqual(member(text, charge), 'held')
        self.assertIn('in the charge or billing block that ends the document', merged(text, charge).note)
        self.assertEqual(member(text, STRANGER), 'held')

    def assert_never_answered(self, text, other, own='2026-10-05'):
        """Another occurrence's date in a closing charge block the guards may miss: asked or read as installed, never
        sent and never a member's answer (the narrow release's second refutation)."""
        self.assertIn(date_lines(text), ([], [f'Date of service: {own}']))
        self.assertEqual(member(text, other), 'held')
        self.assertEqual(member(text, own), 'taken')

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
                      'CHARGE INFORMATION - Date of Service: 2026-10-06\nDiagnosis: anemia\n'):
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
