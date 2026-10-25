"""Regressions for refutation round 6 over validation (round 4d repairs, VALIDATION2).

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores
it), the real span reader and the engine, and pins the controls that must keep their reading. Synthetic text only;
pure functions.
"""
from datetime import date

from tests.test_repairs_r3_validation_b import HEAD, Case, check_of, encounter_check, real

DAY = date(2026, 10, 21)
FOLLOW_UP = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
             'Chief complaint: follow-up after hemorrhoid banding.\nFindings: {line}\nMedical decision making: moderate.\n'
             'Total time: 32 minutes.\n')
BANDING = HEAD + 'Procedure: Hemorrhoid banding\nIndication: Bleeding internal hemorrhoids.\nFindings: {find}\n'
OFFICE_PROCEDURE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                    'Chief complaint: follow-up after hemorrhoid banding.\nProcedure: {line}\n'
                    'Medical decision making: moderate.\nTotal time: 32 minutes.\n')


# --- validation:3: "we" after a time or condition clause states no act of today -------------------------------------

class Validation3TemporalLeadTests(Case):
    """validation:3 (critical, regression against 9a9f403). 'When she presented with bleeding, we banded two columns, and
    today they look healed.' made 46221 READY in a follow-up office note: round 5 validation:2's comma arm accepted any
    lead ending in a comma, so a time or condition clause - or a phrase naming no listed occasion ('At that time,',
    'Back then,', 'On referral,') - introduced a banding that was done at an earlier encounter. Such a lead now introduces
    nothing (hold-only): it opens with a time or condition conjunction, holds a subject or an auxiliary of its own, or
    is a comma-ended phrase that opens with neither a listed introductory word nor 'in'."""

    LEADS = ('When she presented with bleeding,', 'When she was seen in clinic,', 'While she was in the hospital,',
             'Once the bleeding started,', 'At that time,', 'At the time,', 'Back then,', 'On referral,',
             'At her consultation,', 'If she bled,', 'On presentation,', 'After she presented with bleeding,',
             'Whenever she bled,', 'Until she was referred,', 'Since she bled,', 'As soon as she bled,',
             # an introductory word, then a time clause of its own in the same lead
             'Then once the bleeding started', 'Subsequently, once the bleeding started,', 'Then, if needed,',
             # an introductory word naming another occasion by its event
             'During her consultation,', 'Following her referral,', 'During her hospitalization,')

    def test_the_claimed_leads_hold_the_banding_in_a_follow_up_note(self):
        for lead in self.LEADS:
            line = f'{lead} we banded two columns, and today they look healed.'
            with self.subTest(lead=lead):
                proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', line), ('99213', 'Total time: 32 minutes.'))
                self.assertEqual(proposals['46221'].status, 'needs_clarification')
                self.assertNotIn('Documented as performed', check_of(proposals['46221'], 'service.status').detail)

    def test_the_claimed_leads_hold_under_a_procedure_heading_and_in_a_banding_report(self):
        for lead in ('When she presented with bleeding,', 'At that time,', 'On presentation,', 'If she bled,'):
            line = f'{lead} we banded two columns, and today they look healed.'
            with self.subTest(lead=lead, layout='office procedure heading'):
                proposals, _ = real(OFFICE_PROCEDURE.format(line=line), ('46221', line))
                self.assertEqual(proposals['46221'].status, 'needs_clarification')
            line = f'{lead} we banded two columns.'
            with self.subTest(lead=lead, layout='banding report'):
                proposals, _ = real(BANDING.format(find=line), ('46221', line))
                self.assertEqual(proposals['46221'].status, 'needs_clarification')

    def test_controls_an_introductory_phrase_of_today_s_procedure_still_states_the_act(self):
        for line in ('In the left lateral position, we banded two columns today.',
                     'After informed consent, we banded the right posterior column today.',
                     'Using the McGivney ligator, we banded two columns today.',
                     'Under direct anoscopic visualization, we banded the left lateral column today.',
                     'This morning, we banded two columns.', 'Today, we banded two columns.',
                     'Today we banded two internal hemorrhoids.'):
            with self.subTest(line=line):
                proposals, _ = real(FOLLOW_UP.format(line=line), ('46221', line))
                self.assertReady(proposals['46221'])
        for line in ('After informed consent, we banded the right posterior column.',
                     'With the patient in the left lateral position we banded the left lateral column.',
                     'In the left lateral position, we banded the right posterior column.'):
            with self.subTest(line=line, layout='banding report'):
                proposals, _ = real(BANDING.format(find=line), ('46221', line))
                self.assertReady(proposals['46221'])


# --- validation:6: a hedged same-day procedure outside plan, history and indication holds the E/M, whatever ranks first

OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{line}\n'
          'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
VISIT = 'Established patient office visit.'


def _labels():
    from studio.gi.profiles import PROFILES
    return {family: PROFILES[family].label for family in ('gi.egd', 'gi.flex_sig', 'gi.other', 'gi.colonoscopy')}


class Validation6HedgedSameDayProcedureTests(Case):
    """validation:6 (critical, regression against 9a9f403). With 'History of present illness: EGD and colonoscopy last
    month were unremarkable.' (regression:6 made the coordinated pair historical), 'Assessment: EGD was performed today
    and showed esophagitis versus reflux.' left 99214 READY: routing's family aggregate ranks the HPI's historical
    first, and engine._possibly_today asked only for an uncertain family. ARCHITECTURE 5.6 reads every routed mention
    outside plan, history and indication sections that hedges as a possible same-day procedure, so a detected family is
    now read mention by mention too, as gi.other already was (hold-only)."""

    HPI = ('History of present illness: EGD and colonoscopy last month were unremarkable.',
           'History of present illness: Colonoscopy and EGD 2 years ago were normal.',
           'History of present illness: EGD last month was unremarkable.',
           'History of present illness: She had an EGD in 2020.')
    STATEMENTS = ('Assessment: EGD was performed today and showed esophagitis versus reflux.',
                  'Impression: EGD was performed today and showed a Schatzki ring versus a web.',
                  'Assessment: EGD today showed esophagitis versus reflux.')

    def test_the_claimed_notes_hold_the_visit_for_the_egd(self):
        labels = _labels()
        for hpi in self.HPI:
            for statement in self.STATEMENTS:
                with self.subTest(hpi=hpi, statement=statement):
                    proposals, _ = real(OFFICE.format(line=f'Chief complaint: dysphagia.\n{hpi}\n{statement}'),
                                        ('99214', VISIT))
                    self.assertVisitHeld(proposals, f'{labels["gi.egd"]} is possibly performed on the same date')
                    self.assertNotIn(labels['gi.colonoscopy'],
                                     check_of(proposals['99214'], 'em.same_day_procedure').detail)

    def test_round_4_validation_0_s_held_lines_beside_a_past_procedure_in_the_history(self):
        from tests.test_repairs_r4_validation import Validation0DiscussionReleaseRevertedTests as Pinned
        for hpi in ('History of present illness: EGD and flexible sigmoidoscopy last year were normal.',
                    'History of present illness: EGD and colonoscopy last month were unremarkable.',
                    'History of present illness: Flexible sigmoidoscopy in 2020 was normal.'):
            for line, label in Pinned.HELD:
                if label == _labels()['gi.other']:
                    continue  # a banding beside a family named only in the history: validation:7's tests
                with self.subTest(hpi=hpi, line=line):
                    proposals, _ = real(OFFICE.format(line=f'{hpi}\n{line}'), ('99214', VISIT))
                    self.assertVisitHeld(proposals, f'{label} is possibly performed on the same date')

    def test_controls_a_past_procedure_or_a_plan_alone_keeps_the_visit_ready(self):
        for line in ('Chief complaint: dysphagia.\nHistory of present illness: EGD and colonoscopy last month were '
                     'unremarkable.\nAssessment: GERD.',
                     'Chief complaint: dysphagia.\nHistory of present illness: EGD and colonoscopy last month were '
                     'unremarkable.\nAssessment and plan: Possible EGD if symptoms persist.',
                     'Chief complaint: dysphagia.\nHistory of present illness: EGD last month was unremarkable.\n'
                     'Plan: EGD next month if symptoms persist.',
                     'Chief complaint: dysphagia.\nHistory of present illness: She had an EGD in 2020.\n'
                     'Assessment: GERD, controlled.'):
            with self.subTest(line=line):
                proposals, _ = real(OFFICE.format(line=line), ('99214', VISIT))
                self.assertVisitReady(proposals)


from tests.test_repairs_status_r2_validation import placed  # noqa: E402
from tests.test_validation import EM, EngineCase, Note, finding, selected, visit_context  # noqa: E402


class Validation6MentionByMentionTests(EngineCase):
    """validation:6 with constructed routing: which mentions of a detected family not read as done hold the E/M. A
    hedge under Assessment does; a history mention held only by routing's another-time rule does not (round 5
    regression:6: 'EGD and colonoscopy last month were unremarkable.' held every such visit), nor does a plan."""

    NOTE = Note('Date of service: 2026-10-21', 'Established patient office visit.', 'Total time 32 minutes.',
                'EGD in 2019 was normal.', 'EGD and colonoscopy last month were unremarkable.',
                'EGD was performed today and showed esophagitis versus reflux.', 'Possible EGD if symptoms persist.')
    VISIT, TIME = 'Established patient office visit.', 'Total time 32 minutes.'

    def visit_for(self, *mentions, status='historical'):
        self.statuses = {self.TIME: None}
        visit = finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                        facts={'em_basis': 'total time 32 minutes'})
        egd = finding('gi.egd', status, placed(self.NOTE, 'gi.egd', 'historical', 'EGD in 2019 was normal.', 'history',
                                               'historical: 2019 is before the service date'), *mentions)
        result = self.run_engine(self.NOTE, selected('99214', self.NOTE.span(self.TIME)), findings=[visit, egd],
                                 ctx=visit_context())
        return self.proposal(result, '99214')

    def test_a_hedge_under_assessment_holds_the_visit_whatever_the_family_ranks_first(self):
        hedge = placed(self.NOTE, 'gi.egd', 'uncertain', 'EGD was performed today and showed esophagitis versus reflux.',
                       'assessment', 'uncertain: versus')
        for status in ('historical', 'planned', 'negated', 'cancelled'):
            with self.subTest(status=status):
                visit = self.visit_for(hedge, status=status)
                self.assertEqual(visit.status, 'needs_clarification')
                self.assertIn('separate_em', [c.fact for c in visit.clarifications])

    def test_controls_a_history_time_hold_or_a_plan_hedge_alone_does_not(self):
        for mention in (placed(self.NOTE, 'gi.egd', 'uncertain', 'EGD and colonoscopy last month were unremarkable.',
                               'history', "uncertain: another time: 'last month' may date it or another thing in its "
                               'clause'),
                        placed(self.NOTE, 'gi.egd', 'uncertain', 'Possible EGD if symptoms persist.', 'plan',
                               'uncertain: possible')):
            with self.subTest(section=mention.section):
                visit = self.visit_for(mention)
                self.assertEqual(visit.status, 'ready', [c.detail for c in visit.checks])


# --- validation:4: the incomplete-family reason names what decided it, never a procedure the passage does not name -----

COLONOSCOPY_SHORT = (HEAD + 'Procedure: Colonoscopy\nIndication: Rectal bleeding.\nFindings: The colonoscope was advanced '
                     'to the splenic flexure. The visualized colon was normal. Grade 2 internal hemorrhoids were seen on '
                     'retroflexion.\nImpression: Internal hemorrhoids.\n')
EGD_SHORT = (HEAD + 'Procedure: EGD\nFindings: The gastroscope could not be advanced beyond the mid esophagus. A tight '
             'stricture was seen.\nImpression: Stricture.\n')
NAMES_WORDING = 'as incomplete only through what the document says of the procedure it names'


class Validation4IncompleteFamilyReasonTests(Case):
    """validation:4 (high, new defect). A gi.other code citing a sentence that names no procedure, read incomplete only
    through a detected family's document-level judgement ("Grade 2 internal hemorrhoids were seen on retroflexion."
    beside a colonoscopy that stopped at the splenic flexure), was held with the reason "... as incomplete only through
    what the document says of the procedure it names": it names none. The reason now names the family routing
    attributes the passage to; a passage that names the procedure keeps the pinned wording (hold unchanged)."""

    def assertWorded(self, item, family_label):
        texts = [check_of(item, 'service.status').detail] + [c.reason for c in item.clarifications
                                                             if c.fact == 'performed_status']
        self.assertEqual(item.status, 'needs_clarification')
        for text in texts:
            self.assertNotIn('procedure it names', text)
            self.assertIn(f'as incomplete only through what the document says of {family_label}, the procedure '
                          'routing attributes it to', text)

    def test_a_passage_naming_no_procedure_names_the_family_it_is_attributed_to(self):
        labels = _labels()
        for text, code, passage, family in (
                (COLONOSCOPY_SHORT, '46221', 'Grade 2 internal hemorrhoids were seen on retroflexion.', 'gi.colonoscopy'),
                (COLONOSCOPY_SHORT, '46221', 'The visualized colon was normal.', 'gi.colonoscopy'),
                (COLONOSCOPY_SHORT, '46600', 'Grade 2 internal hemorrhoids were seen on retroflexion.', 'gi.colonoscopy'),
                (EGD_SHORT, '43450', 'A tight stricture was seen.', 'gi.egd')):
            with self.subTest(code=code, passage=passage):
                proposals, _ = real(text, (code, passage))
                self.assertWorded(proposals[code], labels[family])

    def test_controls_a_procedure_line_that_names_its_procedure_keeps_the_pinned_wording(self):
        for text, code, passage in ((COLONOSCOPY_SHORT, '46221', 'Procedure: Colonoscopy'),
                                    (EGD_SHORT, '43450', 'Procedure: EGD')):
            with self.subTest(code=code, passage=passage):
                item = real(text, (code, passage))[0][code]
                self.assertEqual(item.status, 'needs_clarification')
                self.assertIn(NAMES_WORDING, check_of(item, 'service.status').detail)
                self.assertNotIn('routing attributes it to', check_of(item, 'service.status').detail)


# --- validation:5: 46221's one-procedure class needs a band word; another ligation stays a possible missed service -----

BAND_REPORT = (HEAD + 'Procedure: Rubber band ligation of internal hemorrhoids\nFindings: Rubber band ligation of the right '
               'anterior column was performed. {second}\n')
BAND_OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: rectal '
               'bleeding.\nAssessment: Rubber band ligation x2 was performed today. {second}\n'
               'Medical decision making: moderate.\n')


class Validation5LigationIsNotBandingTests(Case):
    """validation:5 (high, false green). 46221's one-procedure class took any 'ligation', so a selected banding
    covered an uncoded suture ligation (46945/46946), a hemorrhoidal artery ligation (46948) or a variceal band
    ligation, and services.unproposed PASSed ('Every performed service that routing detected ... has a selected
    proposal'), where 9a9f403 named it. The class now needs a band word (band, bands, banded, banding, RBL), and a
    suture, artery, Doppler, dearterialization or variceal / esophageal name is a sibling, never the banding."""

    SECOND = ('Suture ligation of the left lateral column was performed.',
              'Doppler-guided hemorrhoidal artery ligation was performed.',
              'Hemorrhoidal artery ligation with Doppler guidance was performed.',
              # a ligation with no band word: not named as the banding (fail-closed: named, a reviewer decides)
              'Ligation of the left lateral column was performed.')
    OFFICE_SECOND = ('Suture ligation of a bleeding hemorrhoid was performed today.',
                     'Transanal hemorrhoidal artery ligation was performed today.',
                     'Band ligation of esophageal varices was performed today.')

    def assertNamedMissed(self, result, name):
        check = encounter_check(result, 'services.unproposed')
        self.assertEqual(check.status, 'warn', check.detail)
        self.assertIn(name, check.detail)
        self.assertNotIn('Rubber band ligation', check.detail)

    def test_another_ligation_in_a_banding_report_is_named(self):
        for second in self.SECOND:
            with self.subTest(second=second):
                proposals, result = real(BAND_REPORT.format(second=second),
                                         ('46221', 'Procedure: Rubber band ligation of internal hemorrhoids'))
                self.assertReady(proposals['46221'])
                self.assertNamedMissed(result, second.split(' was ')[0])

    def test_another_ligation_beside_an_office_banding_is_named(self):
        for second in self.OFFICE_SECOND:
            with self.subTest(second=second):
                proposals, result = real(BAND_OFFICE.format(second=second),
                                         ('46221', 'Rubber band ligation x2 was performed today.'))
                self.assertNamedMissed(result, second.split(' was ')[0])

    def test_controls_the_banding_named_twice_is_covered_and_a_hemorrhoidectomy_is_not(self):
        for second in ('Rubber band ligation of the left lateral column was performed.',
                       'Banding of the left lateral column was performed.', 'RBL of a third column was performed.'):
            with self.subTest(second=second):
                proposals, result = real(BAND_REPORT.format(second=second),
                                         ('46221', 'Procedure: Rubber band ligation of internal hemorrhoids'))
                self.assertReady(proposals['46221'])
                self.assertEqual(encounter_check(result, 'services.unproposed').status, 'pass')
        proposals, result = real(BAND_REPORT.format(second='Excisional hemorrhoidectomy was performed.'),
                                 ('46221', 'Procedure: Rubber band ligation of internal hemorrhoids'))
        self.assertNamedMissed(result, 'Excisional hemorrhoidectomy')
