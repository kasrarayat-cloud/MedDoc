"""Regressions for refutation round 5 over validation (round 4c repairs, VALIDATION).

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores
it), the real span reader and the engine, and pins the controls that must keep their reading. Synthetic text only;
pure functions.
"""
import json
from datetime import date

from studio.gi.detect import route
from studio.types import EvidenceSpan, RoutingResult, from_jsonable, to_jsonable
from studio.validation import checks, engine
from tests.test_repairs_r3_validation_b import HEAD, Case, check_of, real
from tests.test_repairs_r4_validation import assess_timed

DAY = date(2026, 10, 21)


def routed(text, day=DAY):
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, day)))))


# --- bounded:4: a hedged passage's other-service question is indexed once per code ----------------------------------

class Bounded4OtherServiceIndexTests(Case):
    """bounded:4 (high). engine._other_service scanned every routed mention for every hedged linked passage: 20,000
    'Possible EGD?' lines cited by 43235 and 43239 took 82 s in assess() (the worker's assess stage has a 60 s
    allowance). The routed mentions are indexed once per code now, with the same overlap answer."""

    def test_many_hedged_passages_over_many_routed_mentions_assess_in_bounded_time(self):
        lines = 10000
        text = HEAD + 'Findings:\n' + 'Possible EGD?\n' * lines
        first = len(HEAD) + len('Findings:\n')
        spans = [(first + 14 * n, first + 14 * n + 13) for n in range(lines)]
        elapsed, result = assess_timed(text, ('43235', spans), ('43239', spans))
        self.assertLess(elapsed, 9.0)  # 17.6 s scanning every mention per passage; about 2.5 s indexed
        self.assertEqual([(p.code, p.status) for p in result.proposals],
                         [('43235', 'needs_clarification'), ('43239', 'needs_clarification')])

    def test_the_indexed_answer_is_the_scan_s_answer(self):
        """The round-5 verifier's mixed case: every hedged passage of every family, in four sections, answered both
        ways; the index must give the scan's answer for each."""
        lines = ['Possible EGD?', 'Possible colonoscopy?', 'Possible EGD and biopsy of the sigmoid colon?',
                 'Established patient office visit today; possible EGD if symptoms persist?',
                 'Colonoscopy with biopsy was performed today; possible EGD?',
                 'It is unclear whether biopsies were taken.', 'Rule out celiac disease?',
                 'Possible hemorrhoid banding?', 'EGD to the second portion of the duodenum.']
        body = []
        for section in ('Findings:', 'Assessment and plan:', 'History of present illness:', 'Procedure:'):
            body += [section] + lines * 2
        text = HEAD + '\n'.join(body) + '\n'
        routing = routed(text)
        families = engine._VAL_family_index(routing)
        answers = {True: 0, False: 0}
        at = len(HEAD)
        for line in text[len(HEAD):].split('\n'):
            if line.strip() and not line.endswith(':'):
                (reading,) = checks.evidence_readings(text, [EvidenceSpan(0, at, at + len(line), line, True)], DAY)
                for family in ('gi.egd', 'gi.colonoscopy', 'gi.office_em', 'gi.other'):
                    scanned = self.scan(reading, family, routing, text)
                    with self.subTest(line=line, family=family):
                        self.assertEqual(engine._other_service(reading, family, families, text), scanned)
                    answers[scanned] += 1
            at += len(line) + 1
        self.assertTrue(answers[True] and answers[False], answers)

    @staticmethod
    def scan(reading, family, routing, text):
        """engine._other_service as it read at 9a9f403: a scan of every routed mention."""
        if reading.status != 'uncertain' or checks.silent(reading.status, reading.cues):
            return False
        named = {f.family for f in routing.findings for m in f.mentions
                 if m.span.start < reading.end and reading.start < m.span.end}
        if family in checks.EM_FAMILIES:
            return 'gi.office_em' not in named
        return bool(named) and family not in named and not checks.names_intervention(text, reading.start, reading.end,
                                                                                      family)


# --- validation:4: an act counts as stated today only when its clause tells no other time ---------------------------

FOLLOW_UP = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
             'Chief complaint: follow-up after hemorrhoid banding.\nFindings: {line}\nMedical decision making: moderate.\n'
             'Total time: 32 minutes.\n')
ANOSCOPY_REPORT = HEAD + 'Procedure: Anoscopy\nIndication: Follow-up after hemorrhoid banding.\nFindings: {line}\n'
BANDING_REPORT = HEAD + 'Procedure: Rubber band ligation of internal hemorrhoids\nFindings: {line}\n'


class Validation4AnotherTimeInTheActsClauseTests(Case):
    """validation:4 (high). names_procedure took any "today" in a stated act's clause as the act's own time, and its
    relative-pronoun guard missed an auxiliary after the pronoun: 46221 was ready ("Documented as performed") for a
    banding done at an earlier visit ("Two columns were banded at her last visit and look healed today.", "The columns
    which have been banded look healed today."). An act whose clause tells another time (routing's own time reader, a
    history cue, a date that is not the date of service), or that follows a relative pronoun and its auxiliaries, is no
    act stated today - and in a procedure report routing's own act mention, read done because its clause says today,
    no longer counts either. Both only hold (section_only), never exclude."""

    HELD = ('Two columns were banded at her last visit and look healed today.',
            'Two columns were banded on 10/07 and look healed today.',
            'Two columns were banded on October 7 and look healed today.',
            'Two columns were banded on Monday and look healed today.',  # 2026-10-21 is a Wednesday
            'Two columns were banded in September and look healed today.',
            'Two columns were banded on 11/07 and look healed today.',
            'The hemorrhoids that had been banded at her last visit look healed today.',
            'The columns which have been banded look healed today.',
            # variants: a history cue of time or place, and further auxiliaries after the pronoun
            'Two columns were banded 3 weeks ago and look healed today.',
            'Two columns were banded last month and look healed today.',
            'Two columns were banded at an outside hospital and look healed today.',
            'The columns which had previously been banded look healed today.',
            'The columns that have already been banded look healed today.')

    def assertHeld(self, item, passage):
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'),
                         [c.detail for c in item.checks])
        self.assertIn('performed_status', [c.fact for c in item.clarifications])
        status = check_of(item, 'service.status')
        self.assertNotIn('Documented as performed', status.detail)
        self.assertIn(f'“{passage}”', status.detail)

    def test_the_claimed_follow_up_findings_hold_46221(self):
        for line in self.HELD:
            with self.subTest(line=line):
                proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', line))
                self.assertHeld(proposals['46221'], line)

    def test_the_e_m_beside_it_reads_the_banding_as_possibly_performed(self):
        line = self.HELD[0]
        proposals, _ = real(FOLLOW_UP.format(line=line), ('99213', 'Total time: 32 minutes.'), ('46221', line))
        self.assertHeld(proposals['46221'], line)
        detail = check_of(proposals['99213'], 'em.same_day_procedure').detail
        self.assertIn('the service reported as 46221 are possibly performed on the same date', detail)
        self.assertNotIn('documented as performed on the same date', detail)

    def test_routing_s_act_mention_in_a_procedure_report_counts_only_without_another_time(self):
        for line in self.HELD[:8]:
            for layout in (ANOSCOPY_REPORT, BANDING_REPORT):
                with self.subTest(line=line, layout=layout[len(HEAD):len(HEAD) + 20]):
                    proposals, _ = real(layout.format(line=line), ('46221', line))
                    self.assertHeld(proposals['46221'], line)

    def test_a_date_in_the_act_s_clause_too_far_for_routing_to_attach_holds(self):
        # A cited fragment: routing attaches no date this far from it, so its section reads it performed; the act's
        # clause still names another date.
        line = ('Two columns were banded, as described in the referral letter that she brought to the visit dated '
                '2026-09-01, and look healed today.')
        proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', 'Two columns were banded'))
        self.assertHeld(proposals['46221'], 'Two columns were banded')

    def test_controls_an_act_stated_today_stays_ready(self):
        cases = [(FOLLOW_UP, line) for line in ('Two columns were banded today and look healthy.',
                                                'Two columns were banded today on 2026-10-21.',
                                                'Two columns were banded today, on Wednesday.',
                                                'Two columns were banded this morning.',
                                                'Today we banded two internal hemorrhoids.')]
        cases += [(ANOSCOPY_REPORT, 'Two columns were banded today and look healthy.'),
                  (BANDING_REPORT, 'Two columns were banded today and look healthy.')]
        for layout, line in cases:
            with self.subTest(line=line, layout=layout[len(HEAD):len(HEAD) + 20]):
                proposals, _ = real(layout.format(line=line), ('46221', line))
                self.assertReady(proposals['46221'])
                self.assertIn('Documented as performed', check_of(proposals['46221'], 'service.status').detail)
        # the banding report's own procedure line still counts beside a findings line about an earlier banding
        text = BANDING_REPORT.format(line=self.HELD[0])
        proposals, _ = real(text, ('46221', 'Rubber band ligation of internal hemorrhoids'))
        self.assertReady(proposals['46221'])


# --- validation:1: the section-only reason is worded from its rule, never "names no procedure" ----------------------

OFFICE_NOTE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
               'Chief complaint: rectal bleeding.\n{body}\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
COLONOSCOPY_REPORT = (HEAD + 'Procedure: Colonoscopy\nIndication: Average-risk screening.\nFindings: The colonoscope was '
                      'advanced to the cecum. The colon was normal.\nImpression: Normal colonoscopy.\n')
RULE_WORDING = 'is not read as documenting that service as done on that date'


class Validation1SectionOnlyReasonWordingTests(Case):
    """validation:1 (high, false statement). The section_only reason said the linked passage "names no procedure"
    although round 4b's rule tests whether it documents the code's OWN procedure as done: "Anoscopy revealed grade 2
    internal hemorrhoids." held for 46600, "Anoscopy showed grade 3 internal hemorrhoids." for 46221 and "Banding sites
    well healed." were all told, in the check and in the clarification, that they name no procedure. The reason is now
    worded from the rule that decided it."""

    def assertRuleWorded(self, item, passage):
        self.assertEqual(item.status, 'needs_clarification', [c.detail for c in item.checks])
        status = check_of(item, 'service.status')
        (reason,) = [c.reason for c in item.clarifications if c.fact == 'performed_status']
        for text in (status.detail, reason):
            self.assertIn(f'“{passage}”', text)
            self.assertIn(RULE_WORDING, text)
            self.assertNotIn('names no procedure', text)

    def assertNeverNamesNoProcedure(self, proposals):
        for item in proposals.values():
            for text in [c.detail for c in item.checks] + [c.reason for c in item.clarifications]:
                self.assertNotIn('names no procedure', text)

    def test_held_passages_that_name_a_procedure(self):
        cases = (
            (OFFICE_NOTE.format(body='Procedure: Anoscopy.\nFindings: Anoscopy revealed grade 2 internal hemorrhoids.'),
             'Anoscopy revealed grade 2 internal hemorrhoids.', '46600'),
            (HEAD + 'Procedure: Anoscopy\nFindings: Anoscopy showed grade 3 internal hemorrhoids. Banding was deferred '
                    'because she takes apixaban.\n', 'Anoscopy showed grade 3 internal hemorrhoids.', '46221'),
            (FOLLOW_UP.format(line='Banding sites well healed.'), 'Banding sites well healed.', '46221'),
            (FOLLOW_UP.format(line='Hemorrhoidectomy scar noted.'), 'Hemorrhoidectomy scar noted.', '46250'),
            (FOLLOW_UP.format(line=Validation4AnotherTimeInTheActsClauseTests.HELD[0]),
             Validation4AnotherTimeInTheActsClauseTests.HELD[0], '46221'),
            (COLONOSCOPY_REPORT, 'The colon was normal.', '46600'),  # a passage that names none: the same wording
        )
        for text, passage, code in cases:
            with self.subTest(passage=passage, code=code):
                proposals, _ = real(text, (code, passage))
                self.assertRuleWorded(proposals[code], passage)

    def test_the_visit_s_own_documentation_is_worded_from_the_rule_too(self):
        text = OFFICE_NOTE.format(body='Procedure: Anoscopy - patient declined.')
        proposals, _ = real(text, ('46600', 'Established patient office visit.'))
        self.assertRuleWorded(proposals['46600'], 'Established patient office visit.')
        self.assertIn('only as E/M documentation', check_of(proposals['46600'], 'service.status').detail)

    def test_the_claimed_inputs_never_say_names_no_procedure(self):
        anoscopy = (HEAD + 'Procedure: Anoscopy\nIndication: Rectal bleeding.\nFindings: Anoscopy revealed grade 2 '
                    'internal hemorrhoids. No fissure.\n')
        banding = HEAD + ('Procedure: Hemorrhoid banding\nIndication: Bleeding internal hemorrhoids.\nFindings: After '
                          'informed consent we banded the right posterior column.\n')
        visit = (HEAD + 'Place of service: Office (POS 11)\nOffice visit and anoscopy were performed today.\n'
                 'Chief complaint: anal itching.\nMedical decision making: low.\nTotal time: 25 minutes.\n')
        for text, passage, code in ((anoscopy, 'Anoscopy revealed grade 2 internal hemorrhoids.', '46600'),
                                    (banding, 'After informed consent we banded the right posterior column.', '46221'),
                                    (visit, 'Office visit and anoscopy were performed today.', '46600')):
            picks = [(code, passage)] + ([('99213', 'Total time: 25 minutes.')] if 'Total time' in text else [])
            with self.subTest(code=code, passage=passage):
                proposals, _ = real(text, *picks)
                self.assertNeverNamesNoProcedure(proposals)


# --- regression:5: a family named only in the history or the plan never takes a same-day procedure ------------------

R5_OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: rectal '
             'bleeding.\n{elsewhere}\nExam: Abdomen soft.\n{procedure}\nAssessment and plan: Internal hemorrhoids. Fiber. '
             'Return in 6 weeks.\nMedical decision making: moderate.\n')
R5_BAND = 'Procedure: Anoscopy with rubber band ligation of two internal hemorrhoids was performed today.'
R5_VISIT = 'Established patient office visit.'


class Regression5HistoricalFamilyKeepsTheProcedureTests(Case):
    """regression:5 (high, declared misread; the same at R4B-BASE and R3B-BASE). An office note's same-day banding
    ("Procedure: Anoscopy with rubber band ligation ... was performed today.") was no gi.other procedure whenever an EGD
    was named anywhere ("History of present illness: EGD in 2020 was normal."): 'band ligation' is an EGD intervention,
    so the historical EGD took it, the office E/M selected alone was ready and services.unproposed passed. An
    intervention in a procedure section is a detected family's now only when that family is named outside the history
    and the plan."""

    ELSEWHERE = ('History of present illness: EGD in 2020 was normal.',
                 'History of present illness: Prior EGD for reflux was normal.',
                 'Plan: EGD next month for dyspepsia.', 'Past medical history: GERD; EGD 2019 normal.',
                 'History of present illness: Colonoscopy in 2020 was normal.',
                 'History of present illness: EUS last year was unremarkable.')
    PROCEDURES = (R5_BAND, 'Procedure: Hemorrhoid banding was performed today.',
                  'Procedure: Anoscopy with biopsy of an anal lesion was performed today.',
                  'Procedure:\n- Anoscopy with rubber band ligation of two internal hemorrhoids was performed today.')

    def test_the_e_m_selected_alone_is_held_and_the_procedure_is_named_as_missed(self):
        from tests.test_repairs_r3_validation_b import encounter_check
        for elsewhere in self.ELSEWHERE:
            for procedure in self.PROCEDURES:
                text = R5_OFFICE.format(elsewhere=elsewhere, procedure=procedure)
                with self.subTest(elsewhere=elsewhere, procedure=procedure):
                    other = routed(text).finding('gi.other')
                    self.assertIsNotNone(other)
                    self.assertEqual(other.status, 'performed')
                    proposals, result = real(text, ('99214', R5_VISIT))
                    self.assertVisitHeld(proposals, 'Other GI service is documented as performed on the same date')
                    self.assertEqual(encounter_check(result, 'services.unproposed').status, 'warn')

    def test_a_deferred_banding_reads_as_its_no_history_control_reads(self):
        procedure = 'Procedure: Hemorrhoid banding was deferred today.'
        control = routed(R5_OFFICE.format(elsewhere='History of present illness: Two weeks of bleeding.',
                                          procedure=procedure)).finding('gi.other')
        found = routed(R5_OFFICE.format(elsewhere=self.ELSEWHERE[0], procedure=procedure)).finding('gi.other')
        self.assertEqual((found.status, [m.status for m in found.mentions]),
                         (control.status, [m.status for m in control.mentions]))
        self.assertNotIn(found.status, ('performed', 'incomplete'))

    def test_controls_a_family_s_own_procedure_text_still_takes_its_intervention(self):
        bare = HEAD
        reports = (
            bare + 'Procedure: EGD\nIndication: Esophageal varices.\nFindings: The gastroscope was advanced to the second '
                   'part of the duodenum. Large esophageal varices.\nBand ligation of three columns was performed.\n',
            bare + 'Procedure: EGD with band ligation of esophageal varices.\nFindings: Large varices.\n',
            # the findings name neither the EGD nor its instrument near the banding: the EGD is still this report's own
            bare + 'Procedure: EGD\nIndication: Varices.\nFindings: Large esophageal varices in the distal esophagus.\n'
                   'Band ligation of three columns was performed.\n',
            # no headings at all
            bare + 'EGD was performed with the gastroscope to the duodenum. Large esophageal varices were seen. Band '
                   'ligation of three columns was performed.\n',
            bare + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nBiopsies of the '
                   'sigmoid colon were taken.\n')
        for text in reports:
            with self.subTest(text=text[len(HEAD):len(HEAD) + 40]):
                self.assertIsNone(routed(text).finding('gi.other'))
        text = reports[0]
        proposals, _ = real(text, ('43244', 'Band ligation of three columns was performed.'))
        self.assertReady(proposals['43244'])

    def test_controls_outside_a_procedure_section_a_name_is_read_as_before(self):
        # The rule moves only interventions written in a procedure, findings or technique section: a history line's
        # banding stays the historical EGD's (no gi.other appears, as at HEAD).
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: rectal '
                'bleeding.\nHistory of present illness: EGD in 2020 was normal; rubber band ligation was done in 2021.\n'
                'Medical decision making: moderate.\n')
        self.assertIsNone(routed(text).finding('gi.other'))

    def test_controls_an_instrument_outside_the_history_names_the_family_s_own_text(self):
        text = (HEAD + 'History of present illness: EGD 2019.\nFindings: The gastroscope was advanced to the duodenum. '
                'Large esophageal varices.\nBand ligation of three columns was performed.\n')
        self.assertIsNone(routed(text).finding('gi.other'))

    def test_controls_a_lower_tract_family_in_the_history_never_took_a_banding(self):
        text = R5_OFFICE.format(elsewhere='History of present illness: Colonoscopy in 2020 was normal.',
                                procedure=R5_BAND)
        self.assertEqual(routed(text).finding('gi.other').status, 'performed')
        proposals, _ = real(text, ('99214', R5_VISIT))
        self.assertVisitHeld(proposals, 'Other GI service is documented as performed on the same date')


# --- declared:7: May reads as every other month ----------------------------------------------------------------------

def eus_line(day, tail):
    return (f'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: {day}\nProcedure: EUS with fine-needle biopsy '
            f'of the pancreatic head mass {tail}\nIndication: Pancreatic head mass on CT.\n')


class Declared7MayLikeEveryOtherMonthTests(Case):
    """declared:7 (high, declared misread; the same at R4B-BASE and R3B-BASE). The 'may' alternative of cues.OTHER_TIME
    'month' took only in/on/during/by/until/early/mid/late and a space - never _MONTH_LEAD's 'end of', 'beginning
    of', 'last' or 'past', the hyphen, the qualifier, or a day - so "EUS ... at the end of May." on 2026-05-21 (or "last
    May." on 2026-10-21) read no time and 43242 was ready, while the same tails with any other month hold."""

    HELD = (('2026-05-21', 'at the end of May.'), ('2026-05-21', 'at the beginning of May.'),
            ('2026-05-21', 'in mid-May.'), ('2026-05-21', 'in late-May.'), ('2026-05-21', 'late-May.'),
            ('2026-05-21', 'in early-May.'), ('2026-05-21', 'on May 3.'), ('2026-05-21', 'by May 3rd.'),
            ('2026-10-21', 'at the end of May.'), ('2026-10-21', 'in mid-May.'), ('2026-10-21', 'last May.'),
            ('2026-10-21', 'this past May.'), ('2026-10-21', 'LAST MAY.'))

    def test_the_claimed_tails_hold_43242(self):
        for day, tail in self.HELD:
            text = eus_line(day, tail)
            line = text.splitlines()[2]
            with self.subTest(day=day, tail=tail):
                self.assertNotEqual(routed(text, date.fromisoformat(day)).finding('gi.eus').status, 'performed')
                proposals, _ = real(text, ('43242', line))
                self.assertEqual(proposals['43242'].status, 'needs_clarification')
                self.assertIn('performed_status', [c.fact for c in proposals['43242'].clarifications])

    def test_controls_the_date_of_service_s_own_may_stays_ready(self):
        for day, tail in (('2026-05-21', 'in May.'), ('2026-05-21', 'on May 21.'), ('2026-05-21', 'during May.'),
                          ('2026-05-21', 'on May 21st.'), ('2026-10-21', 'in October.')):
            text = eus_line(day, tail)
            with self.subTest(day=day, tail=tail):
                proposals, _ = real(text, ('43242', text.splitlines()[2]))
                self.assertReady(proposals['43242'])

    def test_controls_the_modal_verb_is_never_a_month(self):
        from studio.gi import cues
        month = dict(cues.OTHER_TIME)['month']
        for phrase in ('This may represent adenocarcinoma.', 'The last may be benign.',
                       'Symptoms in the past may have resolved.', 'Next may be an EGD.', 'which may be repeated',
                       'Biopsies may be taken at the end of the procedure.'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(month.search(phrase))
        text = eus_line('2026-10-21', 'and three nodes. The last may be benign.')
        proposals, _ = real(text, ('43242', text.splitlines()[2]))
        self.assertReady(proposals['43242'])


# --- regression:6: services coordinated with the first one share its time --------------------------------------------

R6_OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: abdominal '
             'pain.\nHistory of present illness: {line}\nExam: Abdomen soft, nontender.\nAssessment and plan: IBS. Fiber '
             'and follow-up in 3 months.\nMedical decision making: moderate.\n')


class Regression6CoordinatedServicesShareTheirTimeTests(Case):
    """regression:6 (medium over-hold; a regression from 68191f219). _another_familys_anchor made a time 'unclear'
    whenever the nearest member before it was another family than the passage's first service, so in "EGD and
    colonoscopy last month were unremarkable." neither service was dated (both uncertain) and 99214 was held for a
    possible same-day procedure; at R4B-BASE both were historical and 99214 ready. A service coordinated with the
    first one by connectors alone shares its time again; one named apart still holds (round 4 routing:5)."""

    CLAIMED = (('EGD and colonoscopy last month were unremarkable.', ('gi.egd', 'gi.colonoscopy')),
               ('Colonoscopy and EGD were performed last week at an outside facility and were normal.',
                ('gi.egd', 'gi.colonoscopy')),
               ('Seen after an EGD and colonoscopy performed 3 weeks ago.', ('gi.egd', 'gi.colonoscopy')),
               ('She underwent EGD and colonoscopy last month.', ('gi.egd', 'gi.colonoscopy')),
               ('EUS and ERCP last week showed choledocholithiasis, now cleared.', ('gi.eus', 'gi.ercp')),
               ('EGD, colonoscopy and EUS last year were normal.', ('gi.egd', 'gi.colonoscopy', 'gi.eus')))

    def test_the_claimed_lines_read_historical_and_the_visit_is_ready(self):
        for line, families in self.CLAIMED:
            text = R6_OFFICE.format(line=line)
            with self.subTest(line=line):
                routing = routed(text)
                self.assertEqual([routing.finding(f).status for f in families], ['historical'] * len(families))
                proposals, _ = real(text, ('99214', 'Established patient office visit.'))
                self.assertVisitReady(proposals)

    def test_controls_a_service_named_apart_from_the_first_still_holds_its_line(self):
        findings = 'Findings: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n'
        for line in ('Colonoscopy with cold snare polypectomy for iron deficiency anemia after a normal EGD performed '
                     'last week.', 'Colonoscopy with cold snare polypectomy after an EGD last week.',
                     'Colonoscopy for anemia after a normal EGD and flexible sigmoidoscopy performed last month.',
                     'Colonoscopy with cold snare polypectomy for anemia after normal EGD/EUS last week.'):
            text = HEAD + 'Procedure: ' + line + '\nFindings' + findings[len('Findings'):]
            with self.subTest(line=line):
                proposals, _ = real(text, ('45385', 'Procedure: ' + line))
                self.assertNotEqual(proposals['45385'].bucket, 'excluded', proposals['45385'].exclusion_reason)
                self.assertNotEqual(routed(text).finding('gi.colonoscopy').status, 'historical')

    def test_controls_coordinated_services_stated_today_are_never_dated(self):
        # a history section's performance statement that says today holds (as at HEAD); it is never historical
        text = R6_OFFICE.format(line='EGD and colonoscopy were performed today and were normal.')
        routing = routed(text)
        self.assertEqual([routing.finding(f).status for f in ('gi.egd', 'gi.colonoscopy')], ['uncertain', 'uncertain'])


# --- validation:2: a findings sentence of the report's own procedure, and "we" after an introductory phrase ----------

V2_REPORT = HEAD + 'Procedure: {proc}\nIndication: {ind}\nFindings: {find}\nImpression: Findings as described.\n'
V2_BANDING = HEAD + 'Procedure: Hemorrhoid banding\nIndication: Bleeding internal hemorrhoids.\nFindings: {find}\n'


class Validation2OwnProcedureReportOverHoldTests(Case):
    """validation:2 (medium over-hold, from 998d826 and 7dcec928). In a procedure report (no E/M) a findings sentence
    naming the code's own procedure ("Anoscopy revealed grade 2 internal hemorrhoids.", "Paracentesis yielded 4
    liters ...") and a banding stated by "we" after an introductory phrase ("Under anoscopic guidance we banded the right
    posterior column.") were held, approve refused, although both reference commits read them ready. Such a sentence
    counts now when it opens with the code's own procedure as the report's procedure line - read done by routing - names
    it, and "we" may follow an introductory phrase when it acts on an object."""

    FINDINGS = (('Anoscopy', 'Anoscopy revealed grade 2 internal hemorrhoids.', '46600'),
                ('Diagnostic anoscopy', 'Anoscopy showed a small posterior anal fissure.', '46600'),
                ('Esophageal manometry', 'Esophageal manometry showed normal peristalsis.', '91010'),
                ('Anorectal manometry', 'Anorectal manometry showed dyssynergic defecation.', '91122'),
                ('Paracentesis', 'Paracentesis yielded 4 liters of straw-colored fluid.', '49083'),
                ('Rubber band ligation of internal hemorrhoids', 'Rubber band ligation of the right posterior column.',
                 '46221'),
                ('Anoscopy', '- Anoscopy showed grade 2 internal hemorrhoids.', '46600'),
                ('Anoscopy', '1. Anoscopy showed grade 2 internal hemorrhoids.', '46600'))
    WE = ('Under anoscopic guidance we banded the right posterior column.',
          'Using the McGivney ligator we banded two columns.',
          'After informed consent we banded the right posterior column.',
          'With the patient in the left lateral position we banded the left lateral column.',
          'After informed consent, we banded the right posterior column.',
          'Using the McGivney ligator, we banded three columns.',
          'Under direct anoscopic visualization, we banded the left lateral column.',
          'In the left lateral position, we banded the right posterior column.')

    def test_a_findings_sentence_opening_with_the_report_s_own_procedure_counts(self):
        for proc, line, code in self.FINDINGS:
            with self.subTest(line=line, code=code):
                text = V2_REPORT.format(proc=proc, ind='Symptoms.', find=line)
                proposals, _ = real(text, (code, line))
                self.assertReady(proposals[code])
                self.assertIn(f'Documented as performed: “{line}”', check_of(proposals[code], 'service.status').detail)
        # a cited fragment is read in its sentence
        text = V2_REPORT.format(proc='Anoscopy', ind='Symptoms.', find='Anoscopy revealed grade 2 internal hemorrhoids.')
        proposals, _ = real(text, ('46600', 'grade 2 internal hemorrhoids'))
        self.assertReady(proposals['46600'])

    def test_we_after_an_introductory_phrase_states_the_act(self):
        for line in self.WE:
            with self.subTest(line=line):
                proposals, _ = real(V2_BANDING.format(find=line), ('46221', line))
                self.assertReady(proposals['46221'])
        # in an office note the act stated today counts too (as "Today we banded ..." already did)
        line = 'After informed consent we banded the right posterior column today.'
        proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', line))
        self.assertReady(proposals['46221'])

    def test_a_report_that_denies_its_procedure_corroborates_nothing(self):
        # Routing still reads the procedure line done (it reads no mention in these denials), so the findings sentence
        # stays held, as at HEAD.
        for text, code, line in (
                (V2_REPORT.format(proc='Rubber band ligation of internal hemorrhoids', ind='Symptoms.',
                                  find='Banding sites well healed. No banding was performed today.'),
                 '46221', 'Banding sites well healed.'),
                (V2_REPORT.format(proc='Rubber band ligation of internal hemorrhoids', ind='Symptoms.',
                                  find='Banding sites well healed.').replace('Impression: Findings as described.',
                                                                            'Impression: Banding was deferred.'),
                 '46221', 'Banding sites well healed.'),
                (V2_REPORT.format(proc='Anoscopy', ind='Symptoms.', find='Anoscopy revealed grade 2 internal hemorrhoids.')
                 + 'Addendum: Anoscopy was not performed; the patient declined.\n',
                 '46600', 'Anoscopy revealed grade 2 internal hemorrhoids.')):
            with self.subTest(text=text[len(HEAD):]):
                proposals, _ = real(text, (code, line))
                self.assertEqual(proposals[code].status, 'needs_clarification')
        # a plan to repeat it is no doubt about today's
        text = V2_REPORT.format(proc='Anoscopy', ind='Symptoms.', find='Anoscopy revealed grade 2 internal hemorrhoids.') \
            + 'Plan: Repeat anoscopy in 6 months.\n'
        proposals, _ = real(text, ('46600', 'Anoscopy revealed grade 2 internal hemorrhoids.'))
        self.assertReady(proposals['46600'])

    def test_each_sentence_s_lead_is_read_once_however_many_passages_cite_it(self):
        from unittest import mock
        from studio.gi import detect
        from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
        from studio.reference.store import InMemoryReferenceLookup
        from studio.gi.context import extract_context
        body = ('Anoscopy revealed grade 2 internal hemorrhoids ' * 400).strip() + '.'
        text = V2_REPORT.format(proc='Anoscopy', ind='Symptoms.', find=body)
        routing = routed(text)
        first = text.index(body)
        spans = tuple(EvidenceSpan(0, first + k, first + k + 8, text[first + k:first + k + 8], True)
                      for k in range(0, len(body) - 10, 9) if text[first + k:first + k + 8].strip())
        original, calls = detect._procedure_name, []

        def counting(*args, **kwargs):
            calls.append(args[1])
            return original(*args, **kwargs)

        with mock.patch.object(detect, '_procedure_name', counting):
            result = engine.assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text),
                                   routing=routing, reference=InMemoryReferenceLookup((), {}), service_date=DAY,
                                   normalized=NormalizedResponse('corti', 'corti-coding@1', codes=(
                                       ProviderCode('selected', 'cpt', '46600', 'U', spans, index=0),)),
                                   provider_status='succeeded', extraction_status='ok')
        self.assertGreater(len(spans), 1000)
        self.assertEqual(result.proposals[0].status, 'ready')
        self.assertLessEqual(len(calls), 2)  # one read of the sentence's lead, not one per cited passage

    def test_controls_these_stay_held(self):
        cases = (
            # an office note's procedure heading is only uncertain: nothing corroborates the findings sentence
            (OFFICE_NOTE.format(body='Procedure: Anoscopy.\nFindings: Anoscopy revealed grade 2 internal hemorrhoids.'),
             'Anoscopy revealed grade 2 internal hemorrhoids.', '46600'),
            # the report's procedure line is not done
            (V2_REPORT.format(proc='Anoscopy was deferred', ind='Symptoms.',
                              find='Anoscopy revealed grade 2 internal hemorrhoids.'),
             'Anoscopy revealed grade 2 internal hemorrhoids.', '46600'),
            # a history lead, a time or condition lead, another procedure of the same number range, a sibling
            (V2_REPORT.format(proc='Anoscopy', ind='Symptoms.', find='Prior anoscopy showed a fissure.'),
             'Prior anoscopy showed a fissure.', '46600'),
            (V2_REPORT.format(proc='Anoscopy', ind='Symptoms.', find='Before anoscopy, the patient was positioned.'),
             'Before anoscopy, the patient was positioned.', '46600'),
            (V2_REPORT.format(proc='Esophageal manometry', ind='Symptoms.',
                              find='Anorectal manometry showed dyssynergia.'),
             'Anorectal manometry showed dyssynergia.', '91122'),
            (V2_REPORT.format(proc='Rubber band ligation of internal hemorrhoids', ind='Symptoms.',
                              find='Hemorrhoidectomy scar noted.'), 'Hemorrhoidectomy scar noted.', '46250'),
            (V2_REPORT.format(proc='Anoscopy', ind='Symptoms.',
                              find='Anoscopy showed grade 3 internal hemorrhoids. Banding was deferred.'),
             'Anoscopy showed grade 3 internal hemorrhoids.', '46221'),
            # acts only told of: a noun subject before "we", or no object after the act
            (V2_BANDING.format(find='The internal hemorrhoids we banded have resolved.'),
             'The internal hemorrhoids we banded have resolved.', '46221'),
            (FOLLOW_UP.format(line='With the hemorrhoids we banded healed, no treatment was needed today.'),
             'With the hemorrhoids we banded healed, no treatment was needed today.', '46221'),
            (FOLLOW_UP.format(line='Hemorrhoids we banded last month look healed today.'),
             'Hemorrhoids we banded last month look healed today.', '46221'),
            # routing's own act mention in a banding report, with an introductory phrase but no object after the act
            (V2_BANDING.format(find='With the hemorrhoids we banded healed, the patient was discharged.'),
             'With the hemorrhoids we banded healed, the patient was discharged.', '46221'),
            # a sentence opening with the procedure's name that only tells of an earlier act
            (V2_REPORT.format(proc='Rubber band ligation of internal hemorrhoids', ind='Symptoms.',
                              find='Rubber band ligation sites that were banded at the first session have healed.'),
             'Rubber band ligation sites that were banded at the first session have healed.', '46221'),
        )
        for text, passage, code in cases:
            with self.subTest(passage=passage, code=code):
                proposals, _ = real(text, (code, passage))
                self.assertNotEqual(proposals[code].status, 'ready', [c.detail for c in proposals[code].checks])


# --- validation:5: one procedure named twice in its own report is covered by its code --------------------------------

V5_ANOSCOPY = (HEAD + 'Procedure: Anoscopy\nIndication: Rectal bleeding.\nFindings: Anoscopy was performed and showed '
               'grade 2 internal hemorrhoids.\n')
V5_BANDING = HEAD + 'Procedure: Rubber band ligation of internal hemorrhoids\nFindings: Two internal hemorrhoids were banded.\n'
V5_OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: rectal '
             'bleeding.\n{body}\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')


class Validation5OneProcedureNamedTwiceTests(Case):
    """validation:5 (medium over-warn; round 4 validation:13 by another input). A selected gi.other code covered only
    the routed mention its passage speaks for, so a report naming its one procedure on the procedure line and again in
    its findings called the code's own procedure "a possible missed service ... with no selected proposal". A done
    mention that names again the same single procedure as one the code speaks for is covered now; a range sibling (a
    hemorrhoidectomy beside 46221, a capsule endoscopy or another manometry beside 91010) is still named."""

    def unproposed(self, text, *picks):
        from tests.test_repairs_r3_validation_b import encounter_check
        return encounter_check(real(text, *picks)[1], 'services.unproposed')

    def test_the_claimed_reports_pass_whichever_line_is_cited(self):
        for text, code, cited in ((V5_ANOSCOPY, '46600', 'Procedure: Anoscopy'),
                                  (V5_ANOSCOPY, '46600', 'Anoscopy was performed and showed grade 2 internal hemorrhoids.'),
                                  (V5_ANOSCOPY + 'Impression: Grade 2 internal hemorrhoids.\nPlan: Fiber.\n', '46600',
                                   'Procedure: Anoscopy'),
                                  (V5_BANDING, '46221', 'Procedure: Rubber band ligation of internal hemorrhoids'),
                                  (V5_BANDING, '46221', 'Two internal hemorrhoids were banded.'),
                                  # a code whose range is no single procedure: the same name, word for word
                                  (HEAD + 'Procedure: Esophageal manometry\nFindings: Esophageal manometry was performed '
                                          'and showed normal peristalsis.\n', '91010', 'Procedure: Esophageal manometry')):
            with self.subTest(code=code, cited=cited):
                check = self.unproposed(text, (code, cited))
                self.assertEqual(check.status, 'pass', check.detail)

    def test_a_range_sibling_is_still_a_possible_missed_service(self):
        cases = (
            (V5_BANDING + 'Excisional hemorrhoidectomy with ligation of the vascular pedicle was performed today.\n',
             ('46221', 'Procedure: Rubber band ligation of internal hemorrhoids'), 'Excisional hemorrhoidectomy'),
            (V5_OFFICE.format(body='Rubber band ligation x2 was performed today, and excisional hemorrhoidectomy was '
                                   'performed.'),
             ('46221', 'Rubber band ligation x2 was performed today'), 'excisional hemorrhoidectomy'),
            (V5_OFFICE.format(body='Esophageal manometry was performed today.\nCapsule endoscopy was performed today.'),
             ('91010', 'Esophageal manometry was performed today.'), 'Capsule endoscopy'),
            (V5_OFFICE.format(body='Esophageal manometry was performed today.\nAnorectal manometry was performed today.'),
             ('91010', 'Esophageal manometry was performed today.'), 'Anorectal manometry'),
        )
        for text, pick, missed in cases:
            with self.subTest(missed=missed):
                check = self.unproposed(text, pick, ('99213', 'Total time: 32 minutes.')) if 'Total time' in text \
                    else self.unproposed(text, pick)
                self.assertEqual(check.status, 'warn', check.detail)
                self.assertIn(missed, check.detail)
