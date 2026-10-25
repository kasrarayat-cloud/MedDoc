"""A report that denies its own gi.other procedure never stands on routing's reading of it (repair round 4c, lead).

Routing reads a procedure report's "Procedure: Anoscopy" line done whatever a later sentence says ("Anoscopy was not
performed; the patient declined." names no gi.other mention), and a gi.other code citing that line - or another
passage routing's done mention lies in - counted on that reading alone: 46600 was ready beside the denial. Round 4c's
validation:2 follow-up withdrew only its own new arm (a findings sentence opening with the procedure); the same doubt
(checks._VAL_doubted) now withdraws the routed mention and the procedure line themselves. Hold-only: such a passage is
held as section_only, never excluded. Synthetic text only; pure functions.
"""
from tests.test_repairs_r3_validation_b import HEAD, Case, check_of, real

REPORT = HEAD + 'Procedure: {proc}\nIndication: Symptoms.\nFindings: {find}\nImpression: Findings as described.\n'
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
