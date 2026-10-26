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


# --- validation:0, 1, 2, 8; bounded:4, validation:9: the doubt guard reads what routing reads, and only what doubts ----

REPORT = HEAD + 'Procedure: {proc}\n{status}Indication: Rectal bleeding.\nFindings: {find}\nImpression: Findings as described.\n'
OWN = {'46600': ('Anoscopy', 'Anoscopy revealed grade 2 internal hemorrhoids.'),
       '91010': ('Esophageal manometry', 'Esophageal manometry showed normal peristalsis.'),
       '49083': ('Paracentesis', 'Paracentesis yielded 4 liters of straw-colored fluid.'),
       '46221': ('Rubber band ligation of internal hemorrhoids', 'Rubber band ligation of the right posterior column.')}
DECLARED = ('Procedure performed: No', 'Procedure done: No', 'Procedure performed: None', 'Procedure performed: N',
            'Procedure performed: N/A', 'Procedure performed? No', 'Status: Incomplete', 'Status: Pending',
            'Status: On hold', 'Status: TBD', 'Status: Unknown', 'Status: Requested', 'Status: ☒ Pending',
            'Status: ☒ Incomplete', 'Procedure status: Incomplete', 'Status: Discontinued', 'Rescheduled.',
            'Called off.', 'Status: Cancelled.', 'Not performed.', 'Patient declined.')
RULE_WORDING = 'is not read as documenting that service as done on that date'


class Validation0DeclaredDenialTests(Case):
    """validation:0 (critical, regression against 9a9f403) and validation:1 (high, declared misread). The doubt guard
    read only layout sentences holding an own-procedure word, a reference word or an act verb, so a report that says
    'Procedure performed: No' (split into a heading and 'No'), 'Status: Pending' or 'Rescheduled.' corroborated its
    findings sentence (validation:2's arm) and its procedure line (the routed arm): 46600 READY. The guard now also
    reads routing's own structural denials - the done-question answered no on its line, a status line that denies,
    and a short line that denies, cancels or reschedules (detect._denies) - and a sentence that cuts a procedure short
    with no other procedure named ('The anoscope could not be passed ...'). Hold-only."""

    def test_each_declared_denial_holds_the_findings_sentence_and_the_procedure_line(self):
        for code, (proc, find) in OWN.items():
            for status in DECLARED:
                text = REPORT.format(proc=proc, status=f'{status}\n', find=find)
                for passage in (find, f'Procedure: {proc}'):
                    with self.subTest(code=code, status=status, passage=passage):
                        item = real(text, (code, passage))[0][code]
                        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                        self.assertIn(RULE_WORDING, check_of(item, 'service.status').detail)

    def test_a_denial_at_the_end_of_the_report_or_by_the_procedure_s_name_holds(self):
        for code, (proc, find) in (('46600', OWN['46600']), ('46221', OWN['46221'])):
            name = {'46600': 'Anoscopy', '46221': 'Rubber band ligation'}[code]
            for tail in ('Procedure performed: No\n', 'Status: Pending\n', 'Addendum: Rescheduled.\n',
                         f'{name} performed: No\n'):
                text = REPORT.format(proc=proc, status='', find=find) + tail
                for passage in (find, f'Procedure: {proc}'):
                    with self.subTest(code=code, tail=tail, passage=passage):
                        self.assertEqual(real(text, (code, passage))[0][code].status, 'needs_clarification')

    def test_a_longer_sentence_rescheduling_the_procedure_holds(self):
        # too long for the short-line grammar: its own reading, planned by a rescheduling of today's procedure
        line = 'Anoscopy revealed grade 3 internal hemorrhoids.'
        for extra in (' The anoscopy was rescheduled to next week because her anticoagulant had not been held.',
                      '\nAddendum: The anoscopy was rescheduled to next week because her anticoagulant had not been held.'):
            text = REPORT.format(proc='Anoscopy', status='', find=line + extra)
            for passage in (line, 'Procedure: Anoscopy'):
                with self.subTest(extra=extra, passage=passage):
                    self.assertEqual(real(text, ('46600', passage))[0]['46600'].status, 'needs_clarification')

    def test_an_instrument_that_could_not_be_passed_holds(self):
        for code, sentence in (('46600', 'The anoscope could not be passed beyond the anal verge because of pain.'),
                               ('91010', 'The catheter could not be passed through the lower esophageal sphincter.'),
                               ('49083', 'The needle could not be advanced into the larger pocket.')):
            proc, find = OWN[code]
            text = REPORT.format(proc=proc, status='', find=f'{find} {sentence}')
            for passage in (find, f'Procedure: {proc}'):
                with self.subTest(code=code, passage=passage):
                    self.assertEqual(real(text, (code, passage))[0][code].status, 'needs_clarification')

    def test_controls_no_denial_of_today_s_procedure_keeps_the_report_ready(self):
        for code, (proc, find) in OWN.items():
            for status in ('', 'Procedure performed: Yes\n', 'Status: Completed.\n', 'Procedure completed: Yes\n',
                           'Plan: Repeat in 6 months.\n'):
                text = REPORT.format(proc=proc, status=status, find=find)
                for passage in (find, f'Procedure: {proc}'):
                    with self.subTest(code=code, status=status, passage=passage):
                        self.assertReady(real(text, (code, passage))[0][code])


class Validation2ReferenceDenialTests(Case):
    """validation:2 (critical, regression against 9a9f403). A sentence that cuts short 'the procedure' or 'the exam'
    was no doubt when it also named banding ('The procedure was terminated early; banding will be scheduled.'), so the
    anoscopy the report says was terminated was READY. A reference word that is the subject of a denial, cancellation,
    cut or doubt now counts whatever else the sentence names; so does a pronoun with no procedure named before it."""

    EXTRAS = ('The procedure was terminated early; banding will be scheduled.',
              'The procedure was aborted before banding could be performed.',
              'The exam was incomplete; hemorrhoid banding is planned under anesthesia.',
              'The exam was terminated early because of pain, so banding was not attempted.',
              'Because of pain the procedure was stopped and no banding was done.',
              'It was aborted due to pain, and rubber band ligation was deferred.',
              'Banding was considered, but the procedure was aborted because of pain.',
              'The procedure was terminated early; RBL will be scheduled.',
              'The exam was aborted, so no hemorrhoidectomy was considered.',
              'The study was cancelled; ligation is planned.',
              # read only at the reference word ("was attempted" governs the word, not the sentence)
              'The procedure was attempted but abandoned; banding is planned under anesthesia.',
              'The exam was attempted; hemorrhoid banding is planned.')

    def test_the_claimed_sentences_hold_the_findings_sentence_and_the_procedure_line(self):
        line = 'Anoscopy revealed grade 3 internal hemorrhoids.'
        for extra in self.EXTRAS:
            text = REPORT.format(proc='Anoscopy', status='', find=f'{line} {extra}')
            for passage in (line, 'Procedure: Anoscopy'):
                with self.subTest(extra=extra, passage=passage):
                    self.assertEqual(real(text, ('46600', passage))[0]['46600'].status, 'needs_clarification')

    def test_controls_another_procedure_s_denial_is_no_doubt_about_this_one(self):
        line = 'Anoscopy revealed grade 3 internal hemorrhoids.'
        for extra in ('Banding was deferred because she takes apixaban.',
                      'Banding was deferred because it was not indicated.',
                      'Banding was not performed; it was deferred to a later visit.'):
            text = REPORT.format(proc='Anoscopy', status='', find=f'{line} {extra}')
            for passage in (line, 'Procedure: Anoscopy'):
                with self.subTest(extra=extra, passage=passage):
                    self.assertReady(real(text, ('46600', passage))[0]['46600'])


class Validation8AnotherActIsNoDoubtTests(Case):
    """validation:8 (medium over-hold). The guard held ordinary reports whose procedure line every base approved:
    another act's denial ('No biopsies were performed.', 'No sedation was required for the exam.'), another
    procedure qualified as such ('No other procedure was done.'), or a plan line saying no repeat is needed. Such a
    sentence denies another act or a future one, so it is no doubt about today's procedure (restores 9a9f403 for the
    procedure line, R4B-BASE for the findings sentence); a true denial still holds."""

    OTHER = ('No biopsies were performed.', 'Biopsy was not performed.', 'No polypectomy was performed.',
             'Retroflexion was not performed.', 'No sedation was required for the exam.',
             'Photo documentation was not performed.', 'Digital rectal exam was deferred.',
             'No further procedure was performed.', 'No additional procedures were performed.',
             'No other procedure was done.')
    PLAN = {'46221': ('Plan: No further banding is needed.', 'Plan: Repeat banding is not necessary.',
                      'Plan: No repeat banding needed at this time.',
                      'Impression: Successful banding; no further banding needed.'),
            '46600': ('Plan: No repeat anoscopy needed.',),
            '49083': ('Plan: No repeat paracentesis is needed at this time.',),
            '91010': ('Plan: No repeat manometry is needed.',)}

    def test_another_act_denied_keeps_the_procedure_line_ready(self):
        for code, (proc, find) in OWN.items():
            for other in self.OTHER:
                for where in ('addendum', 'findings'):
                    if where == 'addendum':
                        text = REPORT.format(proc=proc, status='', find=find) + f'Addendum: {other}\n'
                    else:
                        text = REPORT.format(proc=proc, status='', find=f'{find} {other}')
                    with self.subTest(code=code, other=other, where=where):
                        self.assertReady(real(text, (code, f'Procedure: {proc}'))[0][code])

    def test_a_plan_saying_no_repeat_is_needed_keeps_the_procedure_line_ready(self):
        for code, lines in self.PLAN.items():
            proc, find = OWN[code]
            for line in lines:
                text = REPORT.format(proc=proc, status='', find=find).replace('Impression: Findings as described.\n',
                                                                                 f'{line}\n')
                with self.subTest(code=code, line=line):
                    self.assertReady(real(text, (code, f'Procedure: {proc}'))[0][code])

    def test_controls_true_denials_still_hold(self):
        for code, (proc, find) in OWN.items():
            name = proc.split()[0]
            for denial in (f'{name} was not performed; the patient declined.', 'The procedure was aborted before insertion.',
                           'It was not performed.', 'No procedure was performed.', 'Sedation was not given; not performed.',
                           'The exam was stopped early because of pain.', 'Called off.', 'Rescheduled.',
                           # read silent as a span here: only routing's next-line denial grammar reads them
                           'Not performed.', 'Patient declined.'):
                text = REPORT.format(proc=proc, status='', find=find) + f'Addendum: {denial}\n'
                with self.subTest(code=code, denial=denial):
                    self.assertEqual(real(text, (code, f'Procedure: {proc}'))[0][code].status, 'needs_clarification')


class Bounded4DoubtGuardCostTests(Case):
    """bounded:4 (high) and validation:9 (medium). The doubt guard read every sentence holding an act verb, 'it',
    'procedure' or a gi.other word, up to five times, each read paying the family judgement's scan of every routed
    service: 'Colonoscopy was performed.' x 14,809 under an anoscopy report failed the assess stage at 60 s after the
    provider request was sent (9a9f403: 16 s), and 'Anoscopy normal.' x 23,000 took 9x 9a9f403. The guard now reads only
    sentences whose wording can doubt (and something they could be about), each with the passage's own reading, under
    a read budget beyond which the whole text counts as doubted (held, never released)."""

    def reads(self, text, code, passage):
        from unittest import mock
        from studio.gi import detect
        from studio.validation import checks
        checks._V2_doubt_index.cache_clear()
        calls = []
        own = detect.own_status_for_span

        def counting(*args, **kwargs):
            calls.append(args[1:3])
            return own(*args, **kwargs)
        with mock.patch.object(detect, 'own_status_for_span', counting):
            item = real(text, (code, passage))[0][code]
        checks._V2_doubt_index.cache_clear()
        return item, len(calls)

    def test_repeated_lines_naming_another_procedure_take_no_guard_reads(self):
        for unit in ('Colonoscopy was performed.\n', 'EGD done.\n'):
            text = (HEAD + 'Procedure: Anoscopy\nFindings: Grade 2 internal hemorrhoids were seen.\n') + unit * 3000
            with self.subTest(unit=unit):
                item, count = self.reads(text, '46600', 'Grade 2 internal hemorrhoids were seen.')
                self.assertEqual(item.status, 'needs_clarification')
                self.assertLessEqual(count, 5)  # the cited passage's own readings, never a read per line

    def test_repeated_sentences_with_no_doubting_word_take_no_guard_reads(self):
        for unit in ('Anoscopy normal. ', 'Anoscopy anoscopy anoscopy anoscopy normal. ', 'It was normal. '):
            text = HEAD + 'Procedure: Anoscopy\nIndication: Bleeding.\nFindings: ' + unit * 2000 + '\n'
            with self.subTest(unit=unit):
                item, count = self.reads(text, '46600', 'Procedure: Anoscopy')
                self.assertReady(item)
                self.assertLessEqual(count, 5)

    def test_beyond_the_read_budget_the_text_counts_as_doubted(self):
        from unittest import mock
        from studio.validation import checks
        text = REPORT.format(proc='Anoscopy', status='', find='Anoscopy revealed grade 2 internal hemorrhoids. '
                             'No fissure was seen. Grade 2 internal hemorrhoids were not bleeding.')
        self.assertReady(real(text, ('46600', 'Procedure: Anoscopy'))[0]['46600'])
        checks._V2_doubt_index.cache_clear()
        with mock.patch.object(checks, '_V2_READ_BUDGET', 1):
            item = real(text, ('46600', 'Procedure: Anoscopy'))[0]['46600']
        checks._V2_doubt_index.cache_clear()
        self.assertEqual(item.status, 'needs_clarification')
        self.assertIn(RULE_WORDING, check_of(item, 'service.status').detail)

    def test_the_review_s_stage_inputs_assess_within_the_deadline(self):
        import time
        for unit, chars in (('Colonoscopy was performed.\n', 200000), ('EGD done.\n', 150000)):
            text = HEAD + 'Procedure: Anoscopy\nFindings: Grade 2 internal hemorrhoids were seen.\n'
            text += unit * ((chars - len(text)) // len(unit))
            with self.subTest(unit=unit):
                started = time.monotonic()
                item = real(text, ('46600', 'Grade 2 internal hemorrhoids were seen.'))[0]['46600']
                self.assertLess(time.monotonic() - started, 40)  # route and assess; 60 s is the stage deadline
                self.assertEqual(item.status, 'needs_clarification')


# --- validation:7: a family named only in the history or the plan takes no same-day procedure, whatever its section ---

def routed(text, day=DAY):
    import json
    from studio.gi.detect import route
    from studio.types import RoutingResult, from_jsonable, to_jsonable
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, day)))))


OF7 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: rectal bleeding.\n'
       'History of present illness: {hpi}\n{statement}\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')


class Validation7SameDayProcedureOutsideProcedureSectionsTests(Case):
    """validation:7 (high, regression against 9a9f403). An office note's 'Assessment: Anoscopy with rubber band ligation
    of two internal hemorrhoids was performed today.' was no gi.other procedure beside 'EGD and colonoscopy last month
    were unremarkable.' in the HPI: outside procedure, findings and technique sections an intervention went to any
    detected family, so 99214 selected alone was ready ('No same-day procedure is detected.'). regression:5's rule now
    applies in every other section to an intervention whose clause states a performance today; another intervention
    there is read as before (accepted residual: 'Assessment: Rubber band ligation x3 was performed, ?fissure.' with no
    today word beside an EGD named only in the history - widening it changed word-salad fuzz texts, gate)."""

    HPI = ('EGD and colonoscopy last month were unremarkable.', 'She underwent EGD and colonoscopy 3 years ago.',
           'EGD in 2020 was normal.', 'EGD last month was unremarkable.')
    STATEMENTS = ('Assessment: Anoscopy with rubber band ligation of two internal hemorrhoids was performed today.',
                  'Impression: Rubber band ligation x3 was completed today.',
                  'Assessment: Internal hemorrhoids, grade 2; rubber band ligation of two columns was performed today.',
                  'Exam: Rubber band ligation x3 was completed today.',
                  'Rubber band ligation x3 was completed today.')

    def test_the_banding_is_a_same_day_procedure_beside_a_past_egd(self):
        from tests.test_repairs_r3_validation_b import encounter_check
        for hpi in self.HPI:
            for statement in self.STATEMENTS:
                text = OF7.format(hpi=hpi, statement=statement)
                with self.subTest(hpi=hpi, statement=statement):
                    other = routed(text).finding('gi.other')
                    self.assertIsNotNone(other)
                    self.assertIn(other.status, ('performed', 'uncertain'))
                    proposals, result = real(text, ('99214', VISIT))
                    self.assertVisitHeld(proposals, 'Other GI service is')
                    if other.status == 'performed':
                        self.assertEqual(encounter_check(result, 'services.unproposed').status, 'warn')

    def test_controls_the_history_s_own_banding_told_at_another_time_stays_the_family_s(self):
        for hpi in ('EGD in 2020 was normal; rubber band ligation was done in 2021.',
                    'EGD with band ligation of varices last month.', 'EGD and band ligation of varices in 2019.'):
            text = OF7.format(hpi=hpi, statement='Assessment: Internal hemorrhoids.')
            with self.subTest(hpi=hpi):
                self.assertIsNone(routed(text).finding('gi.other'))
                if 'last month' not in hpi:  # (a relative time the EGD may not own holds the visit: another rule)
                    self.assertVisitReady(real(text, ('99214', VISIT))[0])


# --- validation:11: a family named only by a mention of another encounter takes no same-day procedure ----------------

O11 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{lines}\nExam: Abdomen soft.\n'
       'Procedure: {procedure}\nAssessment and plan: Internal hemorrhoids. Fiber. Return in 6 weeks.\n'
       'Medical decision making: moderate.\n')


class Validation11NamedOnlyAsAnotherEncounterTests(Case):
    """validation:11 (high, declared misread; the same at every base). regression:5 was only partly repaired: an EGD
    named in the chief complaint, indication, assessment, impression, medications, ROS or an unheaded line ('EGD in 2020
    was normal.') still took an office note's same-day banding, so 99214 selected alone was READY. A family is named
    for an intervention only through a mention outside history and plan sections that is not itself read as another
    encounter's (planned, historical, cancelled or negated)."""

    PLACES = ('Chief complaint: rectal bleeding; EGD 2020 normal.\nHistory of present illness: Two weeks of bleeding.',
              'Indication: Bleeding; EGD in 2020 was normal.\nHistory of present illness: Two weeks of bleeding.',
              'Medications: omeprazole. EGD in 2020 was normal.\nHistory of present illness: Two weeks of bleeding.',
              'Review of systems: negative. EGD in 2020 was normal.\nHistory of present illness: Two weeks of bleeding.',
              'Impression: GERD, EGD in 2020 was normal.\nHistory of present illness: Two weeks of bleeding.',
              'Assessment: GERD; EGD in 2020 was normal.\nHistory of present illness: Two weeks of bleeding.',
              'EGD in 2020 was normal.\nHistory of present illness: Two weeks of bleeding.',
              'Reason for visit: rectal bleeding; EGD in 2020 was normal.\nHistory of present illness: Two weeks.',
              'Diagnoses: GERD (EGD in 2020 was normal).\nHistory of present illness: Two weeks of bleeding.')
    PROCEDURES = ('Anoscopy with rubber band ligation of two internal hemorrhoids was performed today.',
                  'Hemorrhoid banding was performed today.',
                  'Anoscopy with biopsy of an anal lesion was performed today.')

    def test_the_banding_is_a_same_day_procedure_beside_a_past_egd_anywhere(self):
        for lines in self.PLACES:
            for procedure in self.PROCEDURES:
                for control in (False, True):
                    text = O11.format(lines=lines.replace('EGD', 'CT abdomen') if control else lines,
                                      procedure=procedure)
                    with self.subTest(lines=lines, procedure=procedure, control=control):
                        other = routed(text).finding('gi.other')
                        self.assertIsNotNone(other)
                        self.assertEqual(other.status, 'performed')
                        proposals, result = real(text, ('99214', VISIT))
                        self.assertVisitHeld(proposals, 'Other GI service is documented as performed on the same date')
                        self.assertEqual(encounter_check(result, 'services.unproposed').status, 'warn')

    def test_controls_an_egd_named_for_today_still_takes_its_banding(self):
        for text in (HEAD + 'Procedure: EGD\nIndication: Esophageal varices.\nFindings: Large esophageal varices.\n'
                            'Band ligation of three columns was performed.\n',
                     HEAD + 'Indication: Varices; EGD today.\nFindings: Large esophageal varices.\nBand ligation of three '
                            'columns was performed.\n',
                     HEAD + 'Procedure: EGD with band ligation of esophageal varices.\nFindings: Large varices.\n'):
            with self.subTest(text=text[len(HEAD):len(HEAD) + 40]):
                self.assertIsNone(routed(text).finding('gi.other'))


class Validation7OwnCueTests(Case):
    """validation:7's 'stated as performed today' is the intervention's own statement: another procedure's
    'was performed' earlier in a word-salad list (the fuzz corpus's text 2851, synthetic) states nothing of the
    polypectomy after it, so routing reads the text as before (no gi.other procedure, as at HEAD)."""

    TEXT = 'SYNTHETIC TEST DOCUMENT\nDate of service: 2026-10-21\nImpression: risks, benefits, and alternatives of  diagnostic\tdiagnostic , gi\tcold  hot\tendoscopic ,  any capsule endoscopy,was attempted planned\tan\tcomplete   full,capsule endoscopy  was performed prior, an   anoscopy   today endoscopic,outside  diagnostic ,  polypectomy,last month\nPlan: previous, any her\nprocedure , a,and her ,  biopsy  : not performed.\ncold snare polypectomy ,  if needed s/p , colonoscopy ,  (attempted);\nPlan: instead of ,  her ,  2019  for\this\tfollow-up, EGD , if needed\nPlan: previous\nupper endoscopy , today nor ,  gastric his , anoscopy,if needed endoscopic  of\nanoscopy findings\nAssessment: his, follow-up\tprior ,  2019\nlower  any  capsule endoscopy, : not performed\n'

    def test_another_procedure_s_cue_states_nothing_of_the_intervention(self):
        self.assertIsNone(routed(self.TEXT).finding('gi.other'))
