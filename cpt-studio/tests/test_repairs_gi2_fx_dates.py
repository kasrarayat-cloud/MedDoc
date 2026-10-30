"""GI round 2, fix round (session 7c8d38da, fix agent "dates"): the refutation lens "dates" against the integrated head
b8cc7b5b5 (studio/gi/context.py). Each finding was reproduced on that head and on the installed tree (2b82889f) before
anything changed; the target is the installed reading wherever the head moved away from it without the round asking for
it, while the round's intended fixes (ho-04's restoration, the narrow source rule, rule U) still hold.

F1 (must-fix 1). The elapsed-time rule (ho-04) stopped reading "Total time on the date of service: 34 minutes" as a date
this service cannot read. That reading had made the installed tree ASK - by accident - a labelled date it otherwise
sends, so with a time statement added the head sent dates neither installed revision sends. Decided per shape from the
source: where the labelled date is the encounter's own (a date of service beside an earlier outside or index date, a
procedure part that documents its procedure), the send is correct and the installed ask was the misread "34". Where it
is wrong or genuinely uncertain, a structural rule now asks it, with or without a time statement:
- BIRTH: the label's date is the date the document gives as the patient's date of birth ("Encounter date: 01/01/1998"
  beside "DOB: 01/01/1998"): rule N2 says a date of birth is never a service date, so the label is asked and its date
  is never a member's answer (an addendum settles it);
- PART: the label stands in a later numbered part of the document ("PART 2 - PROCEDURE NOTE", "Section B: Procedure
  note", "Part 2: Procedure: Colonoscopy") that documents no procedure - no technique, findings or impression - so its
  date dates the procedure the part only names (a planned colonoscopy, a 2019 procedure note), not a service this note
  documents: asked, and a member's answer equal to it is taken;
- ORDER: the label's date is earlier than a date the note itself gives an earlier occurrence ("DOS: 05/01/2019" beside
  "Index colonoscopy - Encounter date: 10/14/2026"): both cannot be right - asked, a member's answer equal to it taken.

F2. The narrow source rule read negated ("not aborted", "not cancelled"), answered ("Cancelled: No", "Cancellation
reason: N/A"), billing ("Copay: deferred") and today's own ("Status: procedure aborted ...") status words, and
incidental heading words ("Last name:", "Last updated:", "Balance due:", "Requested by:") as marking another occurrence:
today's correct date was asked and a member's correct answer held. Now a status word marks another occurrence only when
it says the dated occurrence did not happen (aborted is not one: an aborted procedure happened on its date), is not
negated (cues.status_negation), is not answered No/N/A/none, and is not the value of a field about something else; a
heading word that may name something else ("last", "due", "requested", ...) governs only beside an occurrence noun or a
coded service's name ("Last colonoscopy:"), never alone.

F3. Rule U asked the footer date of ordinary notes whose header states a previous visit or procedure date. It now
applies only to own labels standing in an AUTHORED addendum part after the body (a line that is "Addendum", "Late
entry" or "Amendment", alone): the date written in an addendum dates the addendum, not what the header dates.

F4. The elapsed-time guards read only the time statement's own field, so a date in the next field of its row ("34 min
| Date: 10/23/2026", "34 minutes; Date: 10/23/2026", "(see note: 10/23/2026)") or in a form they did not read
("(23OCT26)", "(23OCT)", "on X/23") let the head send the header's date where the installed tree asked. Now the time
statement's whole line must hold no date-like token outside its durations and any date-of-service label's own date.

Every text here is synthetic (fictional patients); no network, no database.
"""
from django.test import SimpleTestCase

from studio.gi import context
from tests.test_repairs_7c8_context import DateAssertions, merged_date
from tests.test_repairs_7c8_context3 import COLO_PLAIN, EGD_BODY, ELENA_DATE, HEAD, date_fact

TIME = ('Medical decision making: Moderate.\n'
        'Total time on the date of service: 34 minutes, including record review and counseling.\n')
BODY = ('Procedure: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
        'Findings: A 5 mm sigmoid polyp was removed with a cold snare.\n')
VISIT = ('GI office visit\nPatient: Alex Synthetic (fictional)\n'
         'History of present illness: Synthetic patient seen in clinic for constipation.\n'
         'Assessment: Chronic constipation; due for colonoscopy.\n')
OFFICE_PLAIN = ('GI office visit\nHistory of present illness: Synthetic patient seen in clinic for constipation.\n'
                'Assessment: Chronic constipation.\n')


def timed(text):
    """The same text with an E/M time statement after it and, separately, after its first line."""
    first, rest = text.split('\n', 1)
    return (text + '\n' + TIME, first + '\n' + TIME.split('\n')[1] + '\n' + rest)


def shape(text):
    return ' / '.join(line for line in text.splitlines()[1:6] if line.strip())[:100]


# F1 PART: a later numbered part that documents no procedure (asked, with or without a time statement)
PART_UNDOCUMENTED = (
    (HEAD + VISIT + 'Plan:\nColonoscopy with possible polypectomy.\n\nPART 2 - PROCEDURE NOTE\n'
     'Procedure date: 11/04/2026\n', '2026-11-04'),
    (HEAD + VISIT + 'Plan:\nColonoscopy with possible polypectomy.\nPart 2: Procedure: Colonoscopy    '
     'Procedure date: 11/04/2026\n', '2026-11-04'),
    (HEAD + 'GI office visit\nPlan:\nColonoscopy.\nSection B: Procedure note\nDate of service: 11/04/2026\n',
     '2026-11-04'),
    (HEAD + 'GI office visit\nPast medical history:\nColon polyps.\nPART 2 - PROCEDURE NOTE\n'
     'Date of service: 05/01/2019\nColonoscopy with removal of a tubular adenoma.\n', '2019-05-01'),
    (HEAD + 'GI office visit\nPlan:\nColonoscopy.\nPart II - Procedure report\nProcedure: Colonoscopy\n'
     'Date of service: 11/04/2026\n', '2026-11-04'),
)
# F1 PART controls: a procedure part that documents its procedure, a first part, a date before the parts
PART_DOCUMENTED = (
    (HEAD + 'PART 1 - HISTORY AND PHYSICAL\nHistory of present illness: Synthetic patient with hematochezia.\n'
     'PART 2 - PROCEDURE NOTE\nDate of service: 10/14/2026\n' + BODY, '2026-10-14'),
    (HEAD + 'GI office visit\nHistory of present illness: Synthetic patient seen in clinic.\nPlan:\n'
     'Colonoscopy with possible polypectomy.\nPART 2 - PROCEDURE NOTE\nDate of service: 10/14/2026\n' + BODY,
     '2026-10-14'),
    (HEAD + 'Section 1: Indications\nHematochezia.\nPlan:\nProceed with colonoscopy.\nSection 2: Operative report\n'
     'Date of service: 10/14/2026\n' + BODY, '2026-10-14'),
    (HEAD + 'PART 1 - PROCEDURE NOTE\nDate of service: 10/14/2026\nThe colonoscope was advanced to the cecum and a '
     '5 mm sigmoid polyp was removed with a cold snare.\n', '2026-10-14'),
    (HEAD + 'Date of service: 2026-10-14\nPART 1 - CLINIC VISIT\nAssessment: cirrhosis with ascites.\nPlan:\n'
     '- Adjust diuretics.\nPART 2 - PROCEDURE NOTE: EGD WITH BAND LIGATION\nThe gastroscope was passed to the second '
     'part of the duodenum. Three bands were deployed on the distal esophageal varices.\n', '2026-10-14'),
    (HEAD + 'GI office visit\nPlan:\nColonoscopy.\nPart II - Procedure report\nDate of service: 10/14/2026\n'
     'Impression: one sigmoid polyp removed.\n', '2026-10-14'),
    (HEAD + 'PART 2 - PROCEDURE NOTE\nFindings: A 5 mm sigmoid polyp was removed with a cold snare.\n'
     'Date of service: 10/14/2026\n', '2026-10-14'),
)
# F1 BIRTH: a date of service whose value is the date the document gives as the patient's date of birth
BIRTH_EQUAL = (
    HEAD + 'Encounter date: 01/01/1998\nIndex EGD - Date of Service - 10/27/2026    DOB: 01/01/1998\n' + COLO_PLAIN,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex\nDOB: 01/01/1998\nDate of service: 01/01/1998\n\n'
    + COLO_PLAIN,
    HEAD + 'Colonoscopy report\nDate of service: 01/01/1998    Date of birth: 01/01/1998\n\n' + COLO_PLAIN,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex (DOB 01/01/1998)\nProcedure date: 01/01/1998\n\n'
    + COLO_PLAIN,
)
# F1 ORDER: the note's own date earlier than a date it gives an earlier occurrence
ORDER = (
    (HEAD + 'DOS: 05/01/2019\nIndex colonoscopy - Encounter date: 10/14/2026    DOB: 01/01/1998\n' + EGD_BODY,
     '2019-05-01'),
    (HEAD + 'Encounter date: 01/01/1998\nRecent colonoscopy - Date of service: 11/04/2026\n' + OFFICE_PLAIN,
     '1998-01-01'),
    (HEAD + 'Colonoscopy report\nDate of service: 01/01/1998\nPrior EGD Service date: 10/14/2026\n' + COLO_PLAIN,
     '1998-01-01'),
)
OWN = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n'
# ORDER's controls, each beside the variant that asks (so no control passes because its other label was never read):
# an earlier occurrence dated before; a planned one dated after; a planned word beside the earlier one's; an addendum's
ORDER_PAIRS = (
    (OWN + 'Prior procedure date: 10/01/2026\n' + BODY, OWN + 'Prior procedure date: 10/21/2026\n' + BODY),
    (OWN + 'Next procedure date: 10/14/2029\n' + BODY, OWN + 'Prior procedure date: 10/14/2029\n' + BODY),
    (OWN + 'Previous procedure date: 10/21/2026 (rescheduled)\n' + BODY,
     OWN + 'Previous procedure date: 10/21/2026\n' + BODY),
    (OWN + BODY + '\nAddendum\nMost recent visit date: 10/21/2026\nPathology was reviewed by telephone.\n',
     OWN + 'Most recent visit date: 10/21/2026\n' + BODY),
)
# F1: the shapes whose send is correct - the note's own date of service beside another occurrence's qualified date
OWN_BESIDE_ANOTHER = (
    (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nOutside procedure date: 09/03/2026\n' + BODY,
     '2026-10-14'),
    (HEAD + 'Colonoscopy report\nIndex procedure date: 09/03/2026\nDOS: 10/14/2026\n' + BODY, '2026-10-14'),
    (HEAD + 'Colonoscopy report\nDate of service: 10/21/2026\nRecent colonoscopy for Synthetic, Alex Procedure date: '
     '10/14/2026\n' + COLO_PLAIN, '2026-10-21'),
    (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nOutside colonoscopy:\nProcedure date: 09/03/2026\n'
     'Findings: two adenomas.\n' + COLO_PLAIN, '2026-10-14'),
    (HEAD + 'DOB: 01/01/1998\nDate of service: 10/14/2026\n' + COLO_PLAIN, '2026-10-14'),
)


class WrongOrUncertainDatesAreAskedTests(DateAssertions, SimpleTestCase):
    """F1: asked with or without the time statement the installed tree misread; never a date neither installed
    revision sends."""

    def test_a_numbered_part_that_documents_no_procedure(self):
        for base, value in PART_UNDOCUMENTED:
            for text in (base,) + timed(base):
                with self.subTest(text=shape(text)):
                    self.assert_never(text, value)
                    self.assertIn(context.PART_DATE_NOTE, date_fact(text).note)
                    if 'Procedure date' in text:
                        # gi3 fix round 2 (interpretation 51(c)(2), dates2-6): a procedure date is never an office note's
                        # own date - asked, and no member's answer (context._Candidate.asked)
                        self.assert_never(text, value)
                        self.assert_member_conflict(text, value)
                    else:
                        # asked: the part's own date answers it (a member's choice), another date does not
                        self.assert_question(text, value)

    def test_a_procedure_part_that_documents_its_procedure_is_sent(self):
        for base, value in PART_DOCUMENTED:
            for text in (base,) + timed(base):
                with self.subTest(text=shape(text)):
                    self.assert_document(text, value)
                    self.assert_member_conflict(text, ELENA_DATE)

    def test_a_date_of_service_equal_to_the_date_of_birth(self):
        for base in BIRTH_EQUAL:
            for text in (base,) + timed(base):
                with self.subTest(text=shape(text)):
                    self.assert_never(text, '1998-01-01')
                    fact = date_fact(text)
                    self.assertIn(fact.origin, ('missing', 'conflict'))
                    self.assertIn(context.BIRTH_DATE_NOTE, fact.note)
                    # never a member's answer either: the date of birth is held, with a note that says why
                    merged = merged_date(text, '1998-01-01')
                    self.assertTrue(context.is_member_conflict(merged), merged.note)
                    self.assertIn("the patient's date of birth", merged.note)

    def test_the_rule_reads_only_a_date_the_document_gives_as_a_date_of_birth(self):
        # no birth label anywhere and no earlier occurrence after it: the labelled date is the note's own, as installed
        text = HEAD + 'Colonoscopy report\nDate of service: 01/01/1998\nOutside EGD Service date: 10/14/1997\n' + BODY
        self.assert_document(text, '1998-01-01')
        # a joined header's values are each field's by position: the visit's date is not the date of birth (it stays
        # asked by rule N5, two fields in one, and a member's answer with it is taken - as at the installed revision)
        text = HEAD + 'Visit Date & Date of Birth: 10/14/2026 & 01/01/1998\n' + COLO_PLAIN
        self.assertNotIn(context.BIRTH_DATE_NOTE, date_fact(text).note)
        self.assert_member_date(text, '2026-10-14')
        self.assert_member_conflict(text, '1998-01-01')

    def test_a_date_earlier_than_an_earlier_occurrence_s(self):
        for base, value in ORDER:
            for text in (base,) + timed(base):
                with self.subTest(text=shape(text)):
                    self.assert_never(text, value)
                    self.assertIn(context.ORDER_DATE_NOTE, date_fact(text).note)
                    self.assert_member_date(text, value)  # asked; the note's own date answers it
                    self.assert_member_conflict(text, '2026-10-20')

    def test_order_s_controls_and_the_variants_they_stand_beside(self):
        for sent, asked in ORDER_PAIRS:
            with self.subTest(text=shape(sent)):
                self.assert_document(sent, '2026-10-14')
                self.assert_never(asked, '2026-10-14')
                self.assertIn(context.ORDER_DATE_NOTE, date_fact(asked).note)

    def test_the_note_s_own_date_beside_another_occurrence_s_is_sent(self):
        # the installed tree sends each without a time statement and asked with one only because "34" was read as a
        # date; 057a7d398 lists both dates. The source dates this note by its own label.
        for base, value in OWN_BESIDE_ANOTHER:
            for text in (base,) + timed(base):
                with self.subTest(text=shape(text)):
                    self.assert_document(text, value)
                    self.assert_member_date(text, value)
                    self.assert_member_conflict(text, ELENA_DATE)


REPORT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\nColonoscopy Report\n'
          'Hospital: Saltmarsh General Hospital (fictional), Outpatient Endoscopy Unit\n')
LABEL = 'Date of procedure: 10/19/2026\n'
TAIL = 'Endoscopist: Priya Haldane-Sorensen, MD (fictional)\n\nIndication\nSurveillance after adenoma removal.\n'
PATIENT = 'Patient: Alex Synthetic (fictional), 61-year-old woman\n'
# F2: nothing here names another occurrence: today's date is sent and a member's equal answer taken, as installed
NEUTRAL = (
    REPORT + PATIENT + 'Examination complete, not aborted.\n' + LABEL + TAIL,
    REPORT + PATIENT + 'The procedure was not cancelled.\n' + LABEL + TAIL,
    REPORT + PATIENT + 'Status: procedure aborted at the splenic flexure (poor preparation)\n' + LABEL + TAIL,
    HEAD + '\nIncomplete colonoscopy - aborted\n' + LABEL + TAIL,
    REPORT + PATIENT + 'Visit status: Completed    Cancellation reason: N/A    ' + LABEL + TAIL,
    REPORT + 'Patient: Alex Synthetic | Cancelled: No | ' + LABEL + TAIL,
    REPORT + 'Procedure aborted: No | ' + LABEL + TAIL,
    REPORT + PATIENT + 'Copay: deferred\n' + LABEL + TAIL,
    REPORT + 'Last name:\nFirst name: Alex\n' + LABEL + TAIL,
    REPORT + 'Last updated:\nBy: front desk\n' + LABEL + TAIL,
    REPORT + 'Balance due:\nAmount: $0.00\n' + LABEL + TAIL,
    REPORT + PATIENT + 'Requested by:\nPhysician: Bea Synthetic, MD\n' + LABEL + TAIL,
    REPORT + PATIENT + 'The procedure was never cancelled.\n' + LABEL + TAIL,
    REPORT + PATIENT + 'Cancelled? No.\n' + LABEL + TAIL,
    REPORT + PATIENT + 'Payment: deferred\n' + LABEL + TAIL,
)
# F2: still another occurrence's - asked, never sent (the narrow rule's own family stays closed)
STILL_ANOTHER = (
    REPORT + PATIENT + 'The procedure was cancelled.\n' + LABEL + TAIL,
    REPORT + PATIENT + 'Status: cancelled\n' + LABEL + TAIL,
    REPORT + 'Cancelled: Yes | ' + LABEL + TAIL,
    REPORT + PATIENT + 'Visit status: Pending    Cancellation reason: patient illness    ' + LABEL + TAIL,
    REPORT + 'Date of procedure: 10/19/2026 (postponed)\n' + TAIL,
    # a word that may name something else governs beside an occurrence noun or a coded service's name
    REPORT + 'Last colonoscopy:\nFacility: Synthetic Regional Hospital\n' + LABEL + TAIL,
    REPORT + 'Requested procedure:\nFacility: Synthetic Regional Hospital\n' + LABEL + TAIL,
    REPORT + 'Index procedure:\nFacility: Synthetic Regional Hospital\n' + LABEL + TAIL,
)


class StatusAndHeadingWordsTests(DateAssertions, SimpleTestCase):
    """F2: the narrow source rule reads only words that say another occurrence."""

    def test_negated_answered_billing_today_s_status_and_neutral_headings_change_nothing(self):
        for text in NEUTRAL:
            with self.subTest(text=shape(text)):
                self.assert_document(text, '2026-10-19')
                self.assert_member_date(text, '2026-10-19')
                self.assert_member_conflict(text, ELENA_DATE)

    def test_a_status_or_heading_naming_another_occurrence_still_asks(self):
        for text in STILL_ANOTHER:
            with self.subTest(text=shape(text)):
                self.assert_never(text, '2026-10-19')
                self.assert_member_conflict(text, ELENA_DATE)


OFFICE_TOP = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\nGastroenterology Office Visit\n'
              'Practice: Bramblewood Digestive Health (fictional)\n'
              'Patient: Alex Synthetic (fictional), 58-year-old man\n')
OFFICE_BODY = ('\nChief Complaint\nHeartburn follow-up.\n\nHistory of Present Illness\nHeartburn improved on '
               'omeprazole.\n\nExamination\nAbdomen soft and nontender.\n\nAssessment\nGastroesophageal reflux '
               'disease, improved.\n\nPlan\nContinue omeprazole 20 mg daily. Return in 6 months.\n\n')
PROC_TOP = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\nColonoscopy Report\n'
            'Facility: Larkspur Valley Endoscopy Center (fictional)\nPatient: Alex Synthetic (fictional)\n')
PROC_BODY = ('\nIndication\nSurveillance after adenoma removal.\n\nTechnique\nThe colonoscope was advanced to the '
             'cecum.\n\nFindings\nA 6 mm sigmoid polyp was removed with a cold snare.\n\nImpression\nOne sigmoid polyp '
             'removed.\n\n')
FOOTERS = (
    'Signature\nElectronically signed: Bea Synthetic, MD (fictional)\nDate of service: 10/22/2026\n',
    'Attestation\nI personally performed the service.\nDate of service: 10/22/2026\nSigned: Bea Synthetic, MD\n',
    'Signature\nEncounter date: 10/22/2026\nProvider: Bea Synthetic, MD (fictional)\n',
    'Disposition\nHome.\nDate of service: 10/22/2026\n',
    'Total time: 34 minutes\nDate of service: 10/22/2026\n',
)
OFFICE_HEADERS = ('Last visit date: 07/14/2026\n', 'Previous visit date: 07/14/2026\n', 'Prior DOS: 07/14/2026\n',
                  'Last encounter date: 07/14/2026\n', 'Most recent visit date: 07/14/2026\n', '')
PROC_HEADERS = ('Previous procedure date: 03/15/2021\n', 'Index procedure date: 04/02/2026\n',
                'Last procedure date: 03/15/2021\n', '')


def footer_notes():
    """The refutation's 38 header-and-footer combinations (its Family C; 7 controls without a header date)."""
    for header in OFFICE_HEADERS:
        for footer in FOOTERS:
            yield OFFICE_TOP + header + OFFICE_BODY + footer
    for header in PROC_HEADERS:
        for footer in (FOOTERS[0].replace('Date of service', 'Procedure date'), FOOTERS[1]):
            yield PROC_TOP + header + PROC_BODY + footer


class RuleUReadsOnlyAnAuthoredAddendumTests(DateAssertions, SimpleTestCase):
    """F3: a footer date of service is the note's own; a date written in an authored addendum dates the addendum."""

    def test_a_footer_date_of_service_is_sent_as_installed(self):
        for text in footer_notes():
            with self.subTest(text=text.splitlines()[5] + ' ... ' + text.rstrip().splitlines()[-1]):
                self.assert_document(text, '2026-10-22')
                self.assert_member_date(text, '2026-10-22')
                self.assert_member_conflict(text, ELENA_DATE)

    def test_a_date_in_an_authored_addendum_after_another_occurrence_s_header_is_asked(self):
        top = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nColonoscopy Report (fictional)\n'
               'Outside Procedure date: 10/14/2026\n')
        body = ('\nTechnique:\nThe colonoscope was advanced to the cecum.\n\nFindings:\n'
                'A 6 mm sigmoid polyp was removed with a cold snare.\n\n')
        for heading in ('Addendum', 'Addendum:', 'ADDENDUM', 'Late entry', 'Late Entry:', 'Amendment', '## Addendum'):
            text = top + body + heading + '\nDate of service: 10/21/2026\nPathology was reviewed by telephone.\n'
            with self.subTest(heading=heading):
                self.assert_never(text, '2026-10-21', '2026-10-14')
                self.assert_member_date(text, '2026-10-21')
                self.assert_member_conflict(text, '2026-10-14')
        # no addendum heading - a signature block after the body: the note's own date, as at the installed revision
        text = top + body + 'Signature\nElectronically signed: Bea Synthetic, MD\nDate of service: 10/21/2026\n'
        self.assert_document(text, '2026-10-21')
        # prose naming an addendum is no addendum heading
        self.assert_document(top + body + 'An addendum may follow.\nDate of service: 10/21/2026\n', '2026-10-21')


OFFICE = ('GI Clinic - Office Visit\nPatient: Alex Synthetic    DOB: 01/01/1970\nDate of service: 2026-10-22\n'
          'Provider: Bea Synthetic, MD\n\nHistory of present illness: dysphagia to solids for 3 months.\n'
          'Assessment: dysphagia; EGD scheduled.\nPlan: EGD with possible dilation.\n\n'
          'Medical decision making: Moderate.\n')
SIGNED = '\nElectronically signed by Bea Synthetic, MD\n'


class ElapsedTimeReadsItsWholeLineTests(DateAssertions, SimpleTestCase):
    """F4: a date on the time statement's line keeps the installed reading (asked) - a genuine date conflict."""

    def test_a_date_elsewhere_on_the_time_statement_s_line_is_a_question(self):
        for line in ('Total Time on Date of Service: 34 min | Date: 10/23/2026',
                     'Total time on the date of service: 34 minutes; Date: 10/23/2026',
                     'Total time on the date of service: 34 minutes (see note: 10/23/2026)',
                     'Total time on the date of service: 34 minutes (23OCT26)',
                     'Total time on the date of service: 34 minutes (23OCT)',
                     'Total time on the date of service: 34 minutes on X/23',
                     'Total time on the date of service: 34 minutes on 10/23/2026',
                     'Total time on the date of service: 34 minutes; Thursday',
                     'Visit 10/23/2026 - Total time on the date of service: 34 minutes'):
            text = OFFICE + line + '\n' + SIGNED
            with self.subTest(line=line):
                self.assert_never(text, '2026-10-22')
                self.assert_question(text, '2026-10-22')

    def test_elapsed_time_alone_on_its_line_still_restores_the_date(self):
        # ho-04's own sentence and its kin: the line states no other day
        for line in ('Total time on the date of service: 34 minutes, including record review, history, examination, '
                     'counseling and documentation.',
                     'Total time on the date of service: 120 minutes',
                     'Total time on the date of service: 30-39 minutes',
                     'Total time on the date of service: 34 minutes, including record review and counseling.'):
            text = OFFICE + line + '\n' + SIGNED
            with self.subTest(line=line):
                self.assert_document(text, '2026-10-22')

    def test_a_date_of_service_label_on_the_same_line_is_read_as_a_label(self):
        # a date-of-service label's own date on the line is that label's (and speaks as one), never the time's
        self.assert_document(HEAD + 'Total time on the date of service: 34 minutes. Date of service: 10/23/2026\n',
                             '2026-10-23')
        self.assert_conflict(OFFICE + 'Total time on the date of service: 34 minutes. Date of service: 10/23/2026\n',
                             '2026-10-22', '2026-10-23')
