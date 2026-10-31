"""CPT Studio GI round 3, the narrow release (the owner's decision of 2026-10-30): h2-08's charge block.

The installed reading skips every date label a plan or history section holds, so h2-08's charge block - "Charge
information" / "Date of service: 2026-10-06" at the end of its "Assessment and plan" - was dropped and the header's
contradicted "Date of service: 2026-10-05" was sent. Now, where the installed reading sends a date, a date of service in
the note's own closing charge block (the closed class context.CHARGE_HEADINGS; never a visit or procedure date, never a
history section's block) that states another date makes the date a question, and no date is sent. The question keeps
the document's own evidence only: a member's answer is taken only when it is the document's own date, the one the
installed revision sends, and the block's date is named only as what the lines from the block's first line to the
document's end state (context.CHARGE_DATE_NOTE, charge_date_problem) - those lines may record another occurrence.
Every other fact reads exactly as the installed revision 90377ec6f413 read it, its texts and the answers it takes
included: with no own date the charge block's date stays dropped, and where it already asks, nothing changes. Every
reader reads the date the installed revision sends, so the question holds the date and what hangs on it, never the
reading. Synthetic text only.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

from django.test import SimpleTestCase

from studio import jobs
from studio.gi import context, detect
from studio.gi.sections import layout
from studio import reports, review, serializers
from studio.providers.corti import build_coding_request, normalize_coding_response
from studio.reference.store import MUE, PFS, PrefetchedReferenceLookup
from studio.types import Fact, ReferenceSourceInfo, from_jsonable, to_jsonable
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


def date_lines(text, user_values=None):
    """The date lines of the request the stored facts make: the send path, never the date routing reads."""
    facts = jobs._merged_facts(context.extract_context(text), user_values or {})
    request = build_coding_request('corti', 'test', text, jobs._service_date_of(facts), 10 ** 7)
    return list(request.contexts[1:])


def merged(text, value):
    return context.merge_user_values(context.extract_context(text), {'service_date': value})['service_date']


def member(text, value):
    return 'held' if context.is_member_conflict(merged(text, value)) else 'taken'


def quoted_dates(note):
    """The calendar dates the quotes in a text state (ISO strings)."""
    return {day.isoformat() for quote in re.findall('\u201c([^\u201d]*)\u201d', note)
            for day in (context.date_from_match(m) for m in context.FULL_DATE.finditer(quote)) if day}


def lines_part(problem):
    """What the question says the block's lines state, up to the date the installed reading reads."""
    return problem.rsplit(', while ', 1)[0]


def own_part(problem):
    return problem.rsplit(' is read from ', 1)[1]


def source(key, kind):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS (synthetic rows)', title='Synthetic', release=key, url='',
                               sha256='0' * 64, effective_start='2026-01-01', effective_end='2026-12-31', license_note='',
                               scope_note='')


SOURCES = (source('pfs-test', PFS), source('mue-test', MUE))


def rows_of(global_days):
    return {'pfs-test': {(code, ''): {'status': 'A', 'global_days': days, 'mult_proc': '0', 'endo_base': '', 'pctc': '0'}
                         for code, days in global_days.items()},
            'mue-test': {(code, ''): {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of service edit'},
                                      'rationale': 'Anatomic'} for code in global_days}}


def assessed(text, answer, codes, rows=None):
    """The assess stage's own child on the stored facts, with a provider selecting each code on its passage."""
    stored = jobs._merged_facts(context.extract_context(text), {'service_date': answer} if answer else {})
    day = jobs._service_date_of(stored)
    entries = [{'system': 'cpt', 'code': code, 'display': code, 'alternatives': [],
                'evidences': [{'contextIndex': 0, 'text': passage, 'start': text.index(passage),
                               'end': text.index(passage) + len(passage)}]} for code, passage in codes.items()]
    normalized = normalize_coding_response('corti', build_coding_request('corti', 'corti-coding-v2@cptstudio-1', text, day,
                                                                         10 ** 8),
                                           json.dumps({'codes': entries, 'candidates': [], 'usageInfo': {}}).encode())
    reference = RecordingLookup(SOURCES if rows else (), rows or {}, list(codes))
    _, result = jobs._assess_child(text, day, (), {n: from_jsonable(Fact, v) for n, v in stored.items()}, normalized,
                                   reference, 'succeeded', None, ())
    jobs.release_routing_caches()
    return result, reference


class RecordingLookup(PrefetchedReferenceLookup):
    def __init__(self, *args):
        super().__init__(*args)
        self.days = []

    def lookup(self, code, service_date):
        self.days.append(service_date)
        return super().lookup(code, service_date)


def reason_of(text):
    state = checks.service_date_state(context.extract_context(text), None)
    clarification = checks.service_date_clarification(state)
    return clarification.reason if clarification else None


class ChargeBlockTests(SimpleTestCase):
    def assert_asked(self, text, charge='2026-10-06', own='2026-10-05'):
        """The narrow release: the date is asked and no date is sent. The question names what the block's lines state as
        theirs and the date the installed reading reads, from its own line; its evidence is that line only, so that date is
        a member's answer and the block's never is - nor is it quoted as "the document gives" in a held answer's note. And
        every asked text proves the question literally true of it: its first quote is a line of the document, and each
        stated quote a whole line at or after it (the sixth refutation's dates-n6-1, n6-4 and n6-6)."""
        fact = date_fact(text)
        problem = context.charge_date_problem(fact)
        self.assertEqual(fact.origin, 'conflict', [e.text for e in fact.evidence])
        self.assertIsNotNone(problem, fact.note)
        self.assertEqual({d for e in fact.evidence for d in quoted_dates('\u201c' + e.text + '\u201d')}, {own})
        self.assertEqual(context.documented_values(fact), ())  # no value a member's answer may choose
        self.assertEqual(date_lines(text), [])  # no date is sent
        self.assertTrue(problem.startswith('The lines from \u201c'), problem)
        self.assertIn(charge, quoted_dates(lines_part(problem)))
        self.assertEqual(quoted_dates(own_part(problem)), {own})
        self.assertIn(f', while {own} is read from \u201c', problem)
        lines = [' '.join(line.split()) for line in text.splitlines()]
        heading, *stated = re.findall('\u201c([^\u201d]*)\u201d', lines_part(problem))
        self.assertIn(heading, lines, problem)
        after = lines[len(lines) - 1 - lines[::-1].index(heading):]
        self.assertTrue(stated, problem)
        for line in stated:
            self.assertIn(line, after, problem)
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
        if problem is not None:  # asked: the other date is named as the block's lines' only
            self.assertEqual(quoted_dates(own_part(problem)), {own})

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
                      'Charge Information–Date of Service: 2026-10-06\nDiagnosis: anemia\n',
                      # the fifth refutation's dates-n5-2: a dash bullet before a dash-joined heading
                      '– Charge information – Date of service: 2026-10-06\nCPT: 99214\n',
                      '— Billing — DOS: 10/06/2026\nCPT: 99214\n'):
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

    def test_a_block_that_states_the_documents_own_date_asks_nothing_and_a_later_entry_is_named_as_the_lines(self):
        """The fourth refutation's dates-n4-2 and the fifth's n5-1 and n5-3: a block that states the document's own date
        does not contradict it, whatever entry follows its signature. Elsewhere the question names what the lines from the
        block's first line to the document's end state - never "the block's" date: no word list tells a signature line from
        a field ("Electronic signature: ...", "Signed ABN on file: no")."""
        signed = 'Electronically signed: Synthetic Doctor, MD (fictional), 2026-10-05 17:02\n'
        for tail in ('Charge information\nDate of service: 2026-10-05\nCPT: 99214\n' + signed
                     + 'Telephone encounter (DOS: 10/07/2026): labs reviewed with the patient. No charge.\n',
                     'Charge information\nDate of service: 2026-10-05\nCPT: 99214\n' + signed
                     + 'Telephone call: labs reviewed, no charge\nDate of service: 2026-10-07\n',
                     'Charge information\nDate of service: 2026-10-05\nDate of service: 2026-10-06\nCPT: 99214\n'):
            with self.subTest(tail=tail[-50:]):
                self.assert_installed(HEADER + PLAN + tail)
        # a later entry after the block's own date: both are named, as the lines' dates
        text = (HEADER + PLAN + 'Charge information\nDate of service: 2026-10-06\n' + signed
                + 'Follow-up appointment: DOS 11/04/2026 at 09:00 with Synthetic Doctor (fictional).\n')
        self.assert_asked(text)
        problem = context.charge_date_problem(date_fact(text))
        self.assertEqual(quoted_dates(lines_part(problem)), {'2026-10-06', '2026-11-04'})
        # a block with no date of service of its own, a signature this service does not read, then a telephone entry: asked,
        # its date named as the lines', and every answer taken or held as installed (n5-1)
        text = (HEADER + PLAN + 'Charge information\nCPT: 99214\nICD-10: K74.60, R18.8\n'
                'Electronic signature: Synthetic Doctor, MD (fictional), 2026-10-05 17:02\n'
                'Telephone encounter (DOS: 10/07/2026): labs reviewed with the patient; continue diuretics. No charge.\n')
        self.assert_asked(text, charge='2026-10-07')
        # a field that opens with a signature word stays a field of the block (n5-3)
        for block in ('Billing\nSigned ABN on file: no\nDate of service: 10/06/2026\nCPT: 99214\n',
                      'Charge information\nDictated by: Synthetic Doctor, MD (fictional)\nDate of service: 2026-10-06\n'
                      'CPT: 99214\n'):
            with self.subTest(block=block):
                self.assert_asked(HEADER + PLAN + block)

    def test_a_plan_date_above_the_closing_block_is_not_the_blocks(self):
        """A date label above the last charge heading, still in the plan's reach, is no line of the block: a block with no
        date of its own asks nothing, and one that states another date names its own line only."""
        plan = PLAN + 'Date of service: 2026-10-07\n\n'
        self.assert_installed(HEADER + plan + 'Charge information\nCPT: 99214\n')
        text = HEADER + plan + 'Charge information\nDate of service: 2026-10-06\nCPT: 99214\n'
        self.assert_asked(text)
        self.assertEqual(quoted_dates(lines_part(context.charge_date_problem(date_fact(text)))), {'2026-10-06'})

    def test_routing_reads_what_the_installed_reading_sends_asked_or_held(self):
        """The fifth refutation's dates-n5-4: routing's only way to the document's date is context.service_date_of, and a
        question there read the document with no date - held or unanswered, a dated service went from performed to "service
        date not established". Routing stays the installed reading's in every state, and no date is sent while the question
        stands."""
        proc = (FIXTURES / 'upgrade' / 'proc-charge-block.txt').read_text(encoding='utf-8')
        dated = proc.replace('removed with a cold snare and retrieved.\n',
                             'removed with a cold snare and retrieved.\n'
                             'A diminutive rectal polyp was removed with cold forceps on 2026-10-05.\n')
        self.assertNotEqual(proc, dated)
        own = date(2026, 10, 5)
        for text in (proc, dated, H208):
            with self.subTest(text=text[100:140]):
                self.assert_asked(text)
                self.assertEqual(context.service_date_of(text), own)
                self.assertEqual(detect.route(text), detect.route(text, own))
                stored = to_jsonable(detect.route(text, own))
                for answer, sent in (({}, None), ({'service_date': '2026-10-06'}, None),
                                     ({'service_date': STRANGER}, None), ({'service_date': '2026-10-05'}, own)):
                    facts, service_date, routing = jobs._analyze_child(text, answer, 10 ** 6)
                    self.assertEqual(service_date, sent, answer)  # the send path: a question or a held answer sends none
                    self.assertEqual(routing, stored, answer)
                    self.assertEqual(date_lines(text, answer), [f'Date of service: {sent}'] if sent else [], answer)
        colonoscopy = next(f for f in detect.route(dated).findings if f.family == 'gi.colonoscopy')
        self.assertEqual(colonoscopy.status, 'performed')
        self.assertIn('cold forceps', {fact.value for fact in colonoscopy.facts if fact.name == 'interventions'}.pop())
        # a fact the release leaves alone keeps the no-date reading: the release moves routing only off its own question
        conflict = HEADER.replace('Date of service: 2026-10-05\n', 'Date of service: 2026-10-05\nDate of service: 2026-10-07\n')
        self.assertIsNone(context.service_date_of(conflict + PLAN))

    def test_the_question_says_only_what_is_true_of_the_document(self):
        """The sixth refutation. A guard may read past a billing heading it does not know (n6-1), take a line for a heading
        (n6-5) or a label for a date of service (n6-4), and the installed reading may send a planned date (n6-3): none of
        that may make the sentence false, because it says none of it. It quotes the line it read from and each stated line
        whole, and says the date "is read from" its line."""
        def problem_of(text):
            return context.charge_date_problem(date_fact(text))
        # n6-1: a later billing heading outside the closed class: the question names the line it read from
        text = HEADER + PLAN + 'Charge information\nDate of service: 2026-10-06\nCPT 99214\nFacility billing:\nPOS: 22\n'
        self.assert_asked(text)
        self.assertTrue(problem_of(text).startswith("The lines from \u201cCharge information\u201d to the document's end state"))
        self.assertNotIn('last', problem_of(text))
        # n6-3: a planned procedure's date the installed reading sends is read from its line, never called the document's own
        text = (BANNER + 'Clinic note\nPatient: Synthetic Patient (fictional)\nColonoscopy details\nProcedure date: 11/04/2026\n'
                '\nSubjective\nFollow-up.\n\n' + PLAN + 'Charge information\nDate of service: 10/06/2026\nCPT 99203\n')
        self.assert_asked(text, own='2026-11-04')
        self.assertNotIn("document's own", date_fact(text).note)
        # n6-4 and n6-6: each stated line is quoted whole, so what follows its date is read beside it, and a long label keeps it
        for line in ('Date of service: 10/04/2026 through 10/06/2026', 'Date of service: 10/06/2026 (cancelled)',
                     'Note: date of service 10/06/2026 entered in error, corrected to 10/05/2026',
                     'Timely filing deadline from date of service: 01/04/2027',
                     'Gastroenterology outpatient professional reimbursement date of service: 10/16/2026'):
            with self.subTest(line=line):
                text = HEADER + PLAN + 'Billing\nCPT 99214\n' + line + '\n'
                fact = date_fact(text)
                self.assertEqual(fact.origin, 'conflict')
                self.assertIn('\u201c' + line + '\u201d', problem_of(text))
        self.assertEqual(context.charge_date_own(date_fact(HEADER + PLAN + 'Billing\nDate of service: 10/06/2026 (cancelled)\n')),
                         '2026-10-05')
        # a stated line cannot steer the date the note keeps: the marker's last match is the note's own
        spoof = 'Billing\nDate of service: 10/06/2026, while 2020-01-01 is read from x\n'
        self.assertEqual(context.charge_date_own(date_fact(HEADER + PLAN + spoof)), '2026-10-05')
        self.assertEqual(context.service_date_of(HEADER + PLAN + spoof), date(2026, 10, 5))

    def test_a_dated_ledger_row_is_no_dash_joined_heading(self):
        """The sixth refutation's dates-n6-5: only a bullet is stripped before the dash join, so a date and its dash are no
        bullet. A dash bullet (n5-2) and a numbered heading still read."""
        self.assert_installed(HEADER + PLAN + 'Account activity\n2026-09-14 - Charge - amount: $150.00\n'
                              'Date of service: 2026-10-06\n')
        for block in ('\u2013 Charge information \u2013 Date of service: 2026-10-06\nCPT: 99214\n',
                      '5. Charge information \u2013 Date of service: 2026-10-06\nCPT: 99214\n'):
            with self.subTest(block=block):
                self.assert_asked(HEADER + PLAN + block)

    def test_the_question_holds_the_date_and_never_the_reading(self):
        """The sixth refutation's parity-6-1 and 6-2. Routing read the date the installed reading sends, but the inventory and
        the evidence readers were handed no date: a 2025 colonoscopy read as done on this encounter, and a code documented as
        done today went from ready to excluded. Readers now read that date while the question stands; only the gates keep
        none. So every proposal reads as it does with the document's own date, excluded or not, except that a ready one holds
        on the question. A member's held answer reads the same (parity-7-1): it keeps the dateless request's answer."""
        block = '\nAssessment and plan\nFollow up in clinic.\n\nCharge information\nDate of service: 2026-10-06\n'
        report = (BANNER + 'Patient: Synthetic Patient (fictional)\nDate of service: 2026-10-05\nPlace of service: ASC (POS 24)\n'
                  'Colonoscopy report\nIndication: surveillance after EMR.\nFindings:\n'
                  'After review of prior records a 6 mm polyp in the sigmoid colon was removed by cold snare in 2026.\n'
                  'The colonoscope was advanced to the cecum.\nImpression: adenoma suspected.\n' + block)
        office = (BANNER + 'Office visit note\nPatient: Synthetic Patient (fictional)\nDate of service: 2026-10-05\n'
                  'Place of service: office (POS 11)\nEstablished patient\n\nSubjective\nFollow-up of colon polyps. Colonoscopy in '
                  '2025: a 6 mm polyp in the sigmoid colon was removed by cold snare.\nNo melena.\n\nObjective\nAbdomen soft.\n'
                  'Medical decision making: moderate.\nTotal time on the date of the encounter was 32 minutes.\n' + block)
        # the evidence readers read it too, not only the inventory: with no date this passage read "not established as
        # performed" and its code held, where the date reads it historical and excludes it (mutant E4; two gate documents)
        outside = (BANNER + 'Date of service: 2026-10-05\nOutside records:\nColonoscopy at another facility in 2021.\n'
                   'Prep: good. Extent: cecum.\nProcedure: Colonoscopy with cold snare polypectomy.\n'
                   'Findings: The colonoscope was advanced to the hepatic flexure. A 6 mm sigmoid polyp was removed.\n' + block)
        cases = ((report, {'45385': 'After review of prior records a 6 mm polyp in the sigmoid colon was removed by cold snare in 2026.'},
                  {'45385': 'selected'}),
                 (office, {'45385': 'Colonoscopy in 2025: a 6 mm polyp in the sigmoid colon was removed by cold snare.'},
                  {'45385': 'excluded'}),
                 (outside, {'43239': 'Colonoscopy at another facility in 2021.'}, {'43239': 'excluded'}))
        for text, codes, buckets in cases:
            with self.subTest(codes=list(codes)):
                self.assert_asked(text)
                asked, reference = assessed(text, None, codes)
                answered, answered_reference = assessed(text, '2026-10-05', codes)
                self.assertEqual({p.code: p.bucket for p in asked.proposals}, buckets)
                self.assertEqual({p.code: p.bucket for p in answered.proposals}, buckets)
                self.assertEqual({p.code: p.exclusion_reason for p in asked.proposals},
                                 {p.code: p.exclusion_reason for p in answered.proposals})
                self.assertEqual({p.code: p.rationale for p in asked.proposals},
                                 {p.code: p.rationale for p in answered.proposals})
                self.assertEqual([c.detail for c in asked.encounter_checks if c.id == 'services.inventory'],
                                 [c.detail for c in answered.encounter_checks if c.id == 'services.inventory'])
                self.assertFalse([p for p in asked.proposals if p.status == 'ready'])
                self.assertIn(None, reference.days)  # the gate: the reference the checks read has no date
                self.assertEqual(set(answered_reference.days), {date(2026, 10, 5)})
                held, _ = assessed(text, '2026-10-06', codes)  # the date the question quotes, the natural wrong answer
                self.assertEqual({p.code: (p.bucket, p.exclusion_reason, p.rationale) for p in held.proposals},
                                 {p.code: (p.bucket, p.exclusion_reason, p.rationale) for p in asked.proposals})
        inventory = next(c.detail for c in assessed(office, None, cases[1][1])[0].encounter_checks if c.id == 'services.inventory')
        self.assertIn('Documented but not as done today: colonoscopy (historical)', inventory)
        # with a date nothing changes for a document the release leaves alone: a held answer there reads with no date
        plain = report.replace('Date of service: 2026-10-06\n', 'CPT: 45385\n')
        self.assert_installed(plain)
        self.assertEqual(next(p for p in assessed(plain, '2026-10-01', cases[0][1])[0].proposals if p.code == '45385').bucket,
                         'excluded')

    def test_whether_a_code_is_a_procedure_does_not_wait_on_the_question(self):
        """The seventh refutation's parity-7-2 and pipe7-1. With no fee-schedule row a code counts as procedural (fail-closed),
        so while the question stood a breath test raised a same-day E/M warning and question. The row a reader reads is the
        one the installed reading has; the checks still read no dated reference, so nothing opens on the open date."""
        text = (HEADER + 'A hydrogen breath test was performed in the office today.\n'
                'Total time on the date of the encounter was 32 minutes.\n\n' + PLAN + 'Charge information\n'
                'Date of service: 2026-10-06\n')
        codes = {'99214': 'Total time on the date of the encounter was 32 minutes.',
                 '91065': 'A hydrogen breath test was performed in the office today.'}
        rows = rows_of({'99214': 'XXX', '91065': 'XXX'})
        self.assert_asked(text)
        asked, reference = assessed(text, None, codes, rows)
        answered, _ = assessed(text, '2026-10-05', codes, rows)
        def of(result, code):
            return next(p for p in result.proposals if p.code == code)
        def ids(proposal):
            return {c.id for c in proposal.checks}
        self.assertNotIn('em.same_day_procedure', ids(of(asked, '99214')))
        self.assertEqual(ids(of(asked, '99214')) & {'em.same_day_procedure', 'em.same_day_coverage'},
                         ids(of(answered, '99214')) & {'em.same_day_procedure', 'em.same_day_coverage'})
        self.assertEqual([q.fact for q in asked.clarifications], ['service_date'])
        self.assertEqual({p.code: p.status for p in asked.proposals}, {'99214': 'needs_clarification', '91065': 'needs_clarification'})
        # the gates did not open: the fee-schedule and unit checks read no dated reference while the question stands
        for code in codes:
            checks_of = {c.id: c for c in of(asked, code).checks}
            self.assertEqual(checks_of['pfs.presence'].status, 'not_verified')
            self.assertEqual(checks_of['mue.units'].status, 'not_verified')
            self.assertEqual({c.id: c for c in of(answered, code).checks}['pfs.presence'].status, 'pass')
        self.assertEqual(set(reference.days), {None, date(2026, 10, 5)})

    def test_an_own_date_after_the_block_settles_the_question(self):
        """The seventh refutation's text-3: an addendum stating the date the question names answers it, wherever the line stands
        among the closing lines: it reads as installed, and that date is sent."""
        block = 'Charge information\nDate of service: 2026-10-06\nCPT: 99214\n'
        self.assert_asked(HEADER + PLAN + block)
        text = HEADER + PLAN + block + jobs.addendum_block_text(2, datetime(2026, 10, 31, 8, 0), 'Date of service: 2026-10-05')
        self.assertNotEqual(layout(text).section_at(text.rindex('Date of service')).kind, 'plan')  # the application's own header
        self.assert_installed(text)

    def test_a_running_footer_repeating_the_date_settles_nothing(self):
        """The eighth refutation's delta-2: h2-08 as a PDF whose footer repeats the header's date stopped asking and sent the
        contradicted date. A line beyond the plan that is no addendum is no answer: the block's date still stands against
        it. In h2-08 "Diagnosis:" opens a section, so the footer stands outside the plan."""
        footer = 'Synthetic Patient (fictional) | Date of service: 10/05/2026 | Page 2 of 2\n'
        self.assertNotEqual(layout(H208 + footer).section_at(len(H208) + 40).kind, 'plan')
        self.assert_asked(H208 + footer)

    def test_a_held_answer_with_no_provider_answer_reads_as_installed(self):
        """The eighth refutation's delta-1: held at upload nothing is sent and no answer is kept, so there is nothing to misread
        and no reason to differ from the installed revision, which reads that state with no date. With an answer kept, the
        reading is the date's (test_the_question_holds_the_date_and_never_the_reading)."""
        block = '\nAssessment and plan\nFollow up in clinic.\n\nCharge information\nDate of service: 2026-10-06\n'
        text = (BANNER + 'Office visit note\nPatient: Synthetic Patient (fictional)\nDate of service: 2026-10-05\n'
                'Place of service: office (POS 11)\nEstablished patient\n\nSubjective\nFollow-up of colon polyps. Colonoscopy in '
                '2025: a 6 mm polyp in the sigmoid colon was removed by cold snare.\nNo melena.\n\nObjective\nAbdomen soft.\n'
                'Medical decision making: moderate.\nTotal time on the date of the encounter was 32 minutes.\n' + block)
        self.assert_asked(text)
        stored = jobs._merged_facts(context.extract_context(text), {'service_date': '2026-10-06'})
        self.assertIsNone(jobs._service_date_of(stored))
        _, result = jobs._assess_child(text, None, (), {n: from_jsonable(Fact, v) for n, v in stored.items()}, None,
                                       RecordingLookup((), {}, []), 'not_run', None, ())
        jobs.release_routing_caches()
        inventory = next(c.detail for c in result.encounter_checks if c.id == 'services.inventory')
        self.assertIn('Documented as done on this encounter: colonoscopy (performed)', inventory)
        self.assertEqual(result.proposals, ())

    def test_the_labels_around_the_question_call_it_asked_never_a_conflict(self):
        """The sixth refutation's dates-n6-2: the lines may record another occurrence, so the document may not conflict at all.
        Every reader that labels the fact asks charge_date_problem, as the check does; a real conflict keeps its wording."""
        text = (HEADER + PLAN + 'Charge information\nCPT: 99214\nElectronically signed: Synthetic Doctor, MD (fictional)\n'
                'Telephone encounter (DOS: 10/07/2026): labs reviewed. No charge.\n')
        asked = to_jsonable(date_fact(text))
        conflict = to_jsonable(date_fact(HEADER.replace('Date of service: 2026-10-05\n',
                                                        'Date of service: 2026-10-05\nDate of service: 2026-10-07\n') + PLAN))
        self.assertEqual(asked['origin'], 'conflict')
        self.assertIsNone(context.charge_date_problem(conflict))
        section = reports._context_section({'context': {'facts': {'service_date': asked}}})
        self.assertTrue(section[0].startswith('  Service date: asked \u2014 The lines from \u201cCharge information\u201d'), section[0])
        self.assertNotIn('conflict', section[0])
        section = reports._context_section({'context': {'facts': {'service_date': conflict}}})
        self.assertIn('conflicting documentation', section[0])
        self.assertEqual(review._show_fact(review._fact_value(asked)), 'asked')
        self.assertEqual(review._show_fact(review._fact_value(conflict)), 'conflicting values')

        class Stored:
            facts = {'service_date': asked}
        facts = serializers._context_facts(Stored)
        self.assertTrue(facts['service_date']['date_asked'])
        self.assertFalse(facts['service_date']['member_conflict'])

        class Encounter:
            current_context = Stored
        self.assertTrue(serializers._service_date_asked(Encounter))
        self.assertFalse(serializers._service_date_conflict(Encounter))
        Stored.facts = {'service_date': conflict}
        self.assertFalse(serializers._service_date_asked(Encounter))
        self.assertTrue(serializers._service_date_conflict(Encounter))

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
