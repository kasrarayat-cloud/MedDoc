"""A report that denies its own gi.other procedure never stands on routing's reading of it (repair round 4c, lead).

Routing reads a procedure report's "Procedure: Anoscopy" line done whatever a later sentence says ("Anoscopy was not
performed; the patient declined." names no gi.other mention), and a gi.other code citing that line - or another
passage routing's done mention lies in - counted on that reading alone: 46600 was ready beside the denial. Round 4c's
validation:2 follow-up withdrew only its own new arm (a findings sentence opening with the procedure); the same doubt
(checks._VAL_doubted) now withdraws the routed mention and the procedure line themselves. Hold-only: such a passage is
held as section_only, never excluded. Synthetic text only; pure functions.
"""
from studio.gi.profiles import INVENTORY_FAMILIES, family_for_code
from tests.test_repairs_r3_validation_b import HEAD, Case, check_of, real

REPORT =HEAD + 'Procedure: {proc}\nIndication: Symptoms.\nFindings: {find}\nImpression: Findings as described.\n'
RULE_WORDING = 'is not read as documenting that service as done on that date'


class DeniedProcedureLineTests(Case):
    DENIED = (('Anoscopy', 'Anoscopy revealed grade 2 internal hemorrhoids.',
               'Addendum: Anoscopy was not performed; the patient declined.\n', '46600'),
              ('Anoscopy', 'Anoscopy revealed grade 2 internal hemorrhoids. The procedure was aborted before insertion.',
               '', '46600'),
              ('Anoscopy', 'Grade 2 internal hemorrhoids. It was not performed.', '', '46600'),
              ('Anoscopy', 'Grade 2 internal hemorrhoids.', 'Addendum: The exam was terminated early due to pain.\n',
               '46600'),
              ('Rubber band ligation of internal hemorrhoids', 'Banding sites well healed. No banding was performed today.',
               '', '46221'),
              ('Rubber band ligation of internal hemorrhoids', 'Two internal hemorrhoids.',
               'Addendum: Banding was deferred.\n', '46221'))

    def assertHeldByTheRule(self, item):
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
        self.assertIn(RULE_WORDING, check_of(item, 'service.status').detail)

    def test_the_procedure_line_of_a_report_that_denies_it_holds_the_code(self):
        for proc, find, tail, code in self.DENIED:
            with self.subTest(find=find, tail=tail):
                text = REPORT.format(proc=proc, find=find) + tail
                proposals, _ = real(text, (code, f'Procedure: {proc}'))
                self.assertHeldByTheRule(proposals[code])

    def test_a_routed_check_box_item_of_a_report_that_denies_it_holds_the_code(self):
        # a later check-box line of the procedure section: routing's done mention lies in it (not the first sentence)
        text = (HEAD + 'Procedure: Anorectal procedures\n☒ Anoscopy\nFindings: Grade 2 internal hemorrhoids.\n'
                'Addendum: Anoscopy was not performed; the patient declined.\n')
        proposals, _ = real(text, ('46600', '☒ Anoscopy'))
        self.assertHeldByTheRule(proposals['46600'])
        proposals, _ = real(text.replace('Addendum: Anoscopy was not performed; the patient declined.\n', ''),
                            ('46600', '☒ Anoscopy'))
        self.assertReady(proposals['46600'])

    def test_controls_no_doubt_about_today_s_procedure_keeps_the_line_ready(self):
        for proc, tail, code in (('Anoscopy', '', '46600'),
                                 ('Anoscopy', 'Plan: Repeat anoscopy in 6 months.\n', '46600'),
                                 ('Anoscopy', 'History: Anoscopy in 2019 was normal.\n', '46600'),
                                 ('Anoscopy', 'Addendum: Banding was deferred because she takes apixaban.\n', '46600'),
                                 ('Anoscopy', 'Addendum: No biopsies were taken.\n', '46600'),
                                 ('Rubber band ligation of internal hemorrhoids', 'Plan: Repeat banding in 6 weeks.\n',
                                  '46221')):
            with self.subTest(tail=tail, code=code):
                text = REPORT.format(proc=proc, find='Grade 2 internal hemorrhoids.') + tail
                proposals, _ = real(text, (code, f'Procedure: {proc}'))
                self.assertReady(proposals[code])

    def test_an_explicit_statement_of_the_act_is_read_as_before(self):
        # the passage states the act itself (its own performed cue): not a routing-corroborated passage, unchanged
        text = REPORT.format(proc='Anoscopy', find='Anoscopy was performed today and revealed grade 2 hemorrhoids.')
        proposals, _ = real(text, ('46600', 'Anoscopy was performed today and revealed grade 2 hemorrhoids.'))
        self.assertReady(proposals['46600'])


COLONOSCOPY_SHORT = (HEAD + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the splenic flexure.\n'
                     'Impression: Normal.\n')
COLONOSCOPY_ABORTED = (HEAD + 'Procedure: Colonoscopy\nFindings: The procedure was aborted at the splenic flexure because '
                       'of poor preparation.\nImpression: Poor preparation.\n')
EGD_SHORT = (HEAD + 'Procedure: EGD\nFindings: The gastroscope could not be advanced beyond the mid esophagus.\n'
             'Impression: Stricture.\n')
FAMILY_WORDING = ('reads as performed only by its section, and as incomplete only through what the document says of '
                  'the procedure it names')


class IncompleteFamilyLineTests(Case):
    """Reported by the round-4c-2 PLAN agent: a gi.other code citing the procedure line of a detected family that
    stopped short ("Procedure: Colonoscopy" beside "advanced to the splenic flexure") was READY, "Documented as
    incomplete": the line reads performed by its section and incomplete by the colonoscopy's own extent, which says
    nothing of a hemorrhoid banding. engine._unnamed_other now judges such a reading by the passage's own reading
    before its family's judgement (detect.own_status_for_span), and the held reason says what decided it."""

    def test_a_gi_other_code_citing_another_family_s_incomplete_line_is_held(self):
        for text, code, line in ((COLONOSCOPY_SHORT, '46221', 'Procedure: Colonoscopy'),
                                 (COLONOSCOPY_SHORT, '46600', 'Procedure: Colonoscopy'),
                                 (COLONOSCOPY_ABORTED, '46221', 'Procedure: Colonoscopy'),
                                 (EGD_SHORT, '43450', 'Procedure: EGD')):
            with self.subTest(code=code, text=text[len(HEAD):][:60]):
                item = real(text, (code, line))[0][code]
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                detail = check_of(item, 'service.status').detail
                self.assertIn(FAMILY_WORDING, detail)
                self.assertIn(RULE_WORDING, detail)

    def test_controls_the_family_s_own_codes_and_the_code_s_own_line_read_as_before(self):
        for text, code, line, documented in ((COLONOSCOPY_SHORT, '45378', 'Procedure: Colonoscopy', 'incomplete'),
                                             (EGD_SHORT, '43235', 'Procedure: EGD', 'incomplete'),
                                             (REPORT.format(proc='Anoscopy', find='Grade 2 internal hemorrhoids.'),
                                              '46600', 'Procedure: Anoscopy', 'performed')):
            with self.subTest(code=code):
                item = real(text, (code, line))[0][code]
                self.assertReady(item)
                status = check_of(item, 'service.status').detail
                if family_for_code(code) in INVENTORY_FAMILIES:
                    # engine @4: the documented service decides and words the status; the code's own line shows the
                    # service, and the incomplete examination stays shown
                    self.assertIn(f'is documented as {documented}', status)
                    self.assertEqual(check_of(item, 'evidence.support').status, 'pass')
                    self.assertEqual(check_of(item, 'service.incomplete').status, 'warn')
                else:
                    self.assertIn(f'Documented as {documented}: “{line}”', status)
        # a passage its section alone made performed keeps the plain wording
        item = real(REPORT.format(proc='Anoscopy', find='Grade 2 internal hemorrhoids.'),
                    ('46221', 'Procedure: Anoscopy'))[0]['46221']
        self.assertEqual(item.status, 'needs_clarification')
        detail = check_of(item, 'service.status').detail
        self.assertIn('reads as performed only by its section (', detail)
        self.assertNotIn('as incomplete only through', detail)


class NamedProcedureIncompleteTests(Case):
    """Found by the lead while proving IncompleteFamilyLineTests' controls: "Anoscopy was incomplete because of pain."
    left 46600 READY, "Documented as performed", citing that sentence or the procedure line. Routing reads the clause
    after a gi.other name only for the name (it reads incomplete at "Anoscopy"), while the whole sentence reads
    performed by its section alone, so validation:2's doubt guard (checks._VAL_doubted) never saw the report's own
    statement. A sentence's own-procedure words are now also read on their own; one read negated, cancelled or
    incomplete is a doubt about that procedure."""

    def test_a_report_that_says_its_procedure_was_incomplete_corroborates_nothing(self):
        anoscopy = REPORT.format(proc='Anoscopy', find='Anoscopy was incomplete because of pain.')
        banding = REPORT.format(proc='Rubber band ligation of internal hemorrhoids',
                                find='Two columns. Banding was incomplete due to discomfort.')
        for text, code, line in ((anoscopy, '46600', 'Anoscopy was incomplete because of pain.'),
                                 (anoscopy, '46600', 'Procedure: Anoscopy'),
                                 (banding, '46221', 'Procedure: Rubber band ligation of internal hemorrhoids')):
            with self.subTest(code=code, line=line):
                item = real(text, (code, line))[0][code]
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                self.assertIn(RULE_WORDING, check_of(item, 'service.status').detail)

    def test_controls_no_statement_about_this_procedure_keeps_it_as_before(self):
        ordinary = REPORT.format(proc='Anoscopy', find='Anoscopy revealed grade 2 internal hemorrhoids.')
        for line in ('Anoscopy revealed grade 2 internal hemorrhoids.', 'Procedure: Anoscopy'):
            with self.subTest(line=line):
                self.assertReady(real(ordinary, ('46600', line))[0]['46600'])
        for tail in ('Plan: Repeat anoscopy in 6 months.\n', 'Addendum: Banding was incomplete due to discomfort.\n'):
            with self.subTest(tail=tail):
                text = REPORT.format(proc='Anoscopy', find='Grade 2 internal hemorrhoids.') + tail
                self.assertReady(real(text, ('46600', 'Procedure: Anoscopy'))[0]['46600'])
        # the passage that states the incomplete act itself keeps its own reading
        text = REPORT.format(proc='Anoscopy', find='Anoscopy was terminated because of pain.')
        item = real(text, ('46600', 'Anoscopy was terminated because of pain.'))[0]['46600']
        self.assertReady(item)
        self.assertIn('Documented as incomplete: “Anoscopy was terminated because of pain.”',
                      check_of(item, 'service.status').detail)
