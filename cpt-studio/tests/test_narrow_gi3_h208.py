"""CPT Studio GI round 3, the narrow release (the owner's decision of 2026-10-30): h2-08's charge block.

The installed reading skips every date label a plan or history section holds, so h2-08's charge block - "Charge
information" / "Date of service: 2026-10-06" at the end of its "Assessment and plan" - was dropped and the header's
contradicted "Date of service: 2026-10-05" was sent. Now a charge or billing block's own date of service (the closed
class context.CHARGE_HEADINGS; never a visit or procedure date) speaks against the note's own labelled date: where they
differ it is a conflict, asked, and no date is sent. Everything else reads as the installed revision 90377ec6f413 read
it: with no own date the charge block's date stays dropped, so nothing is ever newly sent. Synthetic text only.
"""
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context
from studio.providers.corti import build_coding_request

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


def member(text, value):
    merged = context.merge_user_values(context.extract_context(text), {'service_date': value})['service_date']
    return 'held' if context.is_member_conflict(merged) else 'taken'


class ChargeBlockTests(SimpleTestCase):
    def assert_conflict(self, text, *values):
        fact = date_fact(text)
        self.assertEqual(fact.origin, 'conflict', [e.text for e in fact.evidence])
        self.assertEqual(set(context.documented_values(fact)), set(values), fact.note)
        self.assertEqual(date_lines(text), [])  # no date is sent
        for value in values:
            self.assertEqual(member(text, value), 'taken', value)
        self.assertEqual(member(text, STRANGER), 'held')

    def assert_installed(self, text, value='2026-10-05'):
        """As the installed revision reads it: the header's own date, sent; a different member date held."""
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('document', value), [e.text for e in fact.evidence])
        self.assertEqual(date_lines(text), [f'Date of service: {value}'])
        self.assertEqual(member(text, STRANGER), 'held')

    def test_h2_08_is_a_conflict_and_no_date_is_sent(self):
        self.assert_conflict(H208, '2026-10-05', '2026-10-06')

    def test_charge_and_billing_blocks_speak_against_the_notes_own_date(self):
        for block in ('Charge information\nDate of service: 2026-10-06\n',
                      'Charges\nDOS: 10/06/2026\n',
                      'BILLING INFORMATION:\nService date: 2026-10-06\n',
                      '5. Charge information\nDate of service: 2026-10-06\n',
                      'Charge information: Date of service: 2026-10-06\n',
                      'Billing & coding\nCPT: 99214\nDate of service: 2026-10-06\n',
                      'Superbill\nDiagnosis: anemia\nDate of encounter: 2026-10-06\n',
                      '## Coding\nEncounter date: 2026-10-06\n'):
            with self.subTest(block=block):
                self.assert_conflict(HEADER + PLAN + block, '2026-10-05', '2026-10-06')

    def test_controls_every_other_block_reads_as_installed(self):
        for block in ('Next appointment\nDate of service: 2026-11-18\n',
                      'Pathology\nDate of service: 2026-10-06\n',
                      'Labs\nDate of service: 2026-10-06\n',
                      'Prior visit charges\nDate of service: 2026-09-01\n',
                      'Charges for the next visit\nDate of service: 2026-11-18\n',
                      'Charge information\n\nDate of service: 2026-10-06\n',  # a blank line ends the block
                      'Charge information\nOffice visit, established patient\nDate of service: 2026-10-06\n',
                      'Charge information\nVisit date: 2026-10-06\n',  # a visit date: a plan may book it
                      'Charge information\nProcedure date: 2026-10-06\n',
                      'Charge information\nNext date of service: 2026-11-18\n'):  # its own words: another occurrence
            with self.subTest(block=block):
                self.assert_installed(HEADER + PLAN + block)

    def test_an_equal_date_changes_nothing(self):
        self.assert_installed(HEADER + PLAN + 'Charge information\nDate of service: 2026-10-05\n')

    def test_with_no_own_date_nothing_is_newly_sent(self):
        text = UNDATED + PLAN + 'Charge information\nDate of service: 2026-10-06\n'
        self.assertEqual(date_fact(text).origin, 'missing')
        self.assertEqual(date_lines(text), [])
        self.assertEqual(member(text, STRANGER), 'taken')  # as installed: the label stays dropped

    def test_a_history_sections_charge_block_too(self):
        text = (HEADER.replace('Subjective\nFollow-up of anemia.\n\n', '') + 'Interval history\nDoing well.\n'
                'Charge information\nDate of service: 2026-10-06\n')
        self.assert_conflict(text, '2026-10-05', '2026-10-06')

    def test_the_heading_reader(self):
        for line in ('Charge information', 'CHARGE INFORMATION:', '5. Charges', '## Billing & coding', '- Superbill -'):
            with self.subTest(line=line):
                self.assertIn(context._heading_words(line), context.CHARGE_HEADINGS)
        for line in ('Prior visit charges', 'Next appointment', 'Charge information for the next visit', 'Billing note'):
            with self.subTest(line=line):
                self.assertNotIn(context._heading_words(line), context.CHARGE_HEADINGS)
