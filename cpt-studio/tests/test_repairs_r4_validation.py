"""Regressions for refutation round 4 over validation (round 4b repairs).

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores
it), the real span reader and the engine, and pins the controls that must keep their reading. Synthetic text only;
pure functions.
"""
from studio.gi.profiles import PROFILES
from tests.test_repairs_r3_validation_b import HEAD, VISIT, Case, check_of, real

OFFICE = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{line}\n'
          'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
FLEX_LABEL = PROFILES['gi.flex_sig'].label
EGD_LABEL = PROFILES['gi.egd'].label
OTHER_LABEL = PROFILES['gi.other'].label


# --- validation:0: a hedge beside a stated act never releases the E/M (round 3b's discussion release reverted) ------

class Validation0DiscussionReleaseRevertedTests(Case):
    """validation:0 (critical, new defect from 7198dd0fc). A hedge about the diagnosis in the sentence that states a
    procedure as performed ("Flexible sigmoidoscopy was performed with biopsies, proctitis versus infection.") left
    routing's mention only its hedge cue, and the discussion-section release then read the procedure as merely weighed:
    the office E/M was ready and approvable beside a same-day procedure. The release is reverted (R3B-BASE reading): in
    an assessment, impression, examination, MDM or time section an uncertain mention that routing saw something in
    holds the E/M again."""

    HELD = (
        ('Impression: Flexible sigmoidoscopy was performed with biopsies, proctitis versus infection.', FLEX_LABEL),
        ('Assessment: Rectal bleeding. Rubber band ligation x3 was performed, ?fissure.', OTHER_LABEL),
        ('Physical examination: Anoscopy was performed and showed grade 2 internal hemorrhoids versus prolapse.',
         OTHER_LABEL),
        ('Physical examination: Abdomen soft. Anoscopy performed? Yes. Grade 2 internal hemorrhoids.', OTHER_LABEL),
        # the same day stated in words outside routing's TODAY list
        ('Impression: Flexible sigmoidoscopy was performed at this visit with biopsies, proctitis versus infection.',
         FLEX_LABEL),
        ('Assessment: Anoscopy was performed in the office and showed grade 2 internal hemorrhoids versus prolapse.',
         OTHER_LABEL),
        ('Assessment: Rectal bleeding. Rubber band ligation x3 was performed during this visit, ?fissure.',
         OTHER_LABEL),
        ('Assessment: EGD was performed at this visit with biopsies, ?Barrett esophagus.', EGD_LABEL),
    )

    def test_the_claimed_inputs_hold_the_visit(self):
        for line, label in self.HELD:
            with self.subTest(line=line):
                proposals, _ = real(OFFICE.format(line=line), ('99214', VISIT))
                self.assertVisitHeld(proposals, f'{label} is possibly performed on the same date')
                self.assertIsNone(check_of(proposals['99214'], 'em.same_day_coverage'))

    def test_a_question_in_the_mdm_line_holds_the_visit(self):
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Medical decision making: moderate; flexible sigmoidoscopy performed? yes, biopsies taken.\n'
                'Total time: 32 minutes.\n')
        proposals, _ = real(text, ('99214', VISIT))
        self.assertVisitHeld(proposals, f'{FLEX_LABEL} is possibly performed on the same date')

    def test_the_round_3_over_hold_returns_with_the_revert(self):
        """Accepted (medium): a procedure only discussed or weighed under Assessment or Impression holds the E/M
        again, as at R3B-BASE. Under Plan it stays released (unchanged)."""
        for line in ('Assessment: GERD, not controlled. Possible EGD if symptoms persist.',
                     'Impression: GERD, not controlled; EGD if symptoms persist.'):
            with self.subTest(line=line):
                proposals, _ = real(OFFICE.format(line=line), ('99214', VISIT))
                self.assertVisitHeld(proposals, f'{EGD_LABEL} is possibly performed on the same date')
        proposals, _ = real(OFFICE.format(line='Plan: Possible EGD if symptoms persist.'), ('99214', VISIT))
        self.assertVisitReady(proposals)


# --- validation:1, contract:3, evidence:1, release:1: no XXX test-code discount (round 3b's discount removed) --------

V7 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: {cc}\n{body}\n'
      'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
MANOMETRY = 'Esophageal manometry was performed today.'
BANDING = 'Rubber band ligation x3 completed today.'


class NoCodedTestDiscountTests(Case):
    """validation:1, contract:3, evidence:1 and release:1 (critical, new defects from 8b4a17862). A selected XXX test
    code (91010, 91122) discounted every one-procedure-word gi.other mention its evidence covered, so a same-day banding,
    dilation or anoscopy in the test code's passage, or named after a comma in its sentence, no longer held the office
    E/M. The discount is removed and the R3B-BASE hold restored: a routed gi.other procedure holds the E/M whatever code
    cites it."""

    CASES = (
        # validation:1: the test code cites a sentence that also states a banding or an anoscopy
        ('91122', 'Anorectal manometry was performed today, followed by rubber band ligation of two columns.', None),
        ('91122', 'Anorectal manometry was performed today, and rubber band ligation x3 was completed.', None),
        ('91122', 'Anorectal manometry was performed today; anoscopy was also performed.', None),
        ('91010', 'Esophageal manometry was performed today, and rubber band ligation x3 was completed.', None),
        ('91010', f'{MANOMETRY} {BANDING}', None),
        ('91010', f'{MANOMETRY} {BANDING}', BANDING),  # the test code citing the banding sentence alone
        # contract:3 and evidence:1: the test code's passage spans a second procedure's sentence or line
        ('91010', f'{MANOMETRY}\nHemorrhoid banding was performed today.', None),
        ('91010', f'{MANOMETRY} Esophageal dilation was performed today with a 54 Fr bougie.', None),
        ('91010', f'{MANOMETRY}\nEsophageal dilation was performed today with a 54 Fr bougie.', None),
        ('91010', 'Esophageal manometry was performed today, followed by esophageal dilation with a 54 Fr bougie.',
         None),
        ('91122', 'Anorectal manometry was performed today.\nRubber band ligation of an internal hemorrhoid was '
                  'performed today.', None),
        # release:1: the second procedure named after a comma, so routing's name stops before it
        ('91122', 'Procedure: Anorectal manometry, followed by rubber band ligation of two internal hemorrhoids.',
         None),
        ('91122', 'Procedure note: Anorectal manometry was performed, followed by rubber band ligation of two internal '
                  'hemorrhoids.', None),
        ('91122', 'Procedure: Anorectal manometry; rubber band ligation of two internal hemorrhoids.', None),
        ('91122', 'Procedure: Anorectal manometry, then rubber band ligation x2.', None),
        ('91122', 'Procedure: Anorectal manometry, followed by anoscopy with banding of two internal hemorrhoids.',
         None),
        ('91010', 'Procedure: Esophageal manometry, followed by esophageal dilation with a 54 Fr Maloney bougie.', None),
        ('91010', 'Procedure: Esophageal manometry. Anoscopy.', 'Esophageal manometry'),
    )

    def test_a_same_day_procedure_in_the_test_code_s_passage_holds_the_visit(self):
        for code, body, cited in self.CASES:
            with self.subTest(code=code, body=body, cited=cited):
                text = V7.format(cc='dysphagia and rectal bleeding.', body=body)
                passage = cited or (body[len('Procedure: '):] if body.startswith('Procedure: ') else body)
                proposals, _ = real(text, ('99213', VISIT), (code, passage))
                self.assertVisitHeld(proposals, f'{OTHER_LABEL} is ', '99213')
                self.assertIsNone(check_of(proposals['99213'], 'em.same_day_coverage'))

    def test_the_round_3_over_hold_returns_with_the_removal(self):
        """Accepted (medium): a diagnostic test coded XXX held the E/M before round 3b, and holds it again."""
        for code, line in (('91010', MANOMETRY), ('91122', 'Anorectal manometry was performed today.')):
            with self.subTest(code=code):
                proposals, _ = real(V7.format(cc='dysphagia.', body=line), ('99213', VISIT), (code, line))
                self.assertVisitHeld(proposals, f'{OTHER_LABEL} is documented as performed', '99213')
                self.assertReady(proposals[code])


# --- validation:7 and validation:13: which gi.other procedure a selected code's passage speaks for ------------------

TIME = 'Total time: 32 minutes.'
TWO = 'Rubber band ligation x3 was completed today, and incision and drainage of a perianal abscess was performed.'
TWO_TESTS = 'Esophageal manometry was performed today, and rubber band ligation x3 was completed.'
ONE_RUN_ON = ('Rubber band ligation was performed today. Three bands were placed on the right anterior, right posterior '
              'and left lateral columns.')


class OtherProcedureCoverageTests(Case):
    """validation:7 (high) and validation:13 (medium). A gi.other code covered every procedure of a sentence it cited
    (services.unproposed passed although an incision and drainage, or a banding beside a manometry, had no proposal),
    and covered nothing once its passage ran past its one procedure's sentence (the selected banding was called a
    possible missed service). A passage speaks for a procedure when it overlaps that procedure's sentence and no other
    done procedure's sentence, or holds that procedure's name and no other done procedure's name."""

    def unproposed(self, line, *picks):
        from tests.test_repairs_r3_validation_b import encounter_check
        _, result = real(OFFICE.format(line=line), ('99213', TIME), *picks)
        return encounter_check(result, 'services.unproposed')

    def test_one_clause_of_a_two_procedure_sentence_covers_only_its_procedure(self):
        check = self.unproposed(TWO, ('46221', 'Rubber band ligation x3 was completed today'))
        self.assertEqual(check.status, 'warn')
        self.assertIn('Possible missed service: Other GI service (“and incision and drainage of a perianal abscess”)',
                      check.detail)
        self.assertNotIn('Rubber band ligation', check.detail)
        check = self.unproposed(TWO_TESTS, ('91010', 'Esophageal manometry was performed today'))
        self.assertEqual(check.status, 'warn')
        self.assertIn('Other GI service (“and rubber band ligation x3”)', check.detail)
        self.assertNotIn('manometry', check.detail)

    def test_a_whole_two_procedure_sentence_covers_neither(self):
        for line, code, names in (
                (TWO, '46221', '“Rubber band ligation x3” and “and incision and drainage of a perianal abscess”'),
                (TWO_TESTS, '91010', '“Esophageal manometry” and “and rubber band ligation x3”'),
                ('Anorectal manometry was performed today, and rubber band ligation x3 was completed.', '91122',
                 '“Anorectal manometry” and “and rubber band ligation x3”')):
            with self.subTest(code=code):
                check = self.unproposed(line, (code, line))
                self.assertEqual(check.status, 'warn')
                self.assertIn(f'Possible missed service: Other GI service ({names})', check.detail)

    def test_a_passage_past_its_one_procedure_s_sentence_covers_it(self):
        labelled = 'Procedure: Rubber band ligation of internal hemorrhoids x3 was performed today.'
        broken = ONE_RUN_ON.replace('today. Three', 'today.\nThree')
        after_the_name = ONE_RUN_ON[len('Rubber band ligation '):]  # past the sentence, without the name
        for line, picks in ((ONE_RUN_ON, (('46221', ONE_RUN_ON),)), (broken, (('46221', broken),)),
                            (labelled, (('46221', labelled),)), (ONE_RUN_ON, (('46221', after_the_name),)),
                            (f'Anoscopy was performed today.\n{ONE_RUN_ON}',
                             (('46600', 'Anoscopy was performed today.'), ('46221', ONE_RUN_ON)))):
            with self.subTest(line=line):
                self.assertEqual(self.unproposed(line, *picks).status, 'pass')

    def test_controls(self):
        # each procedure of one sentence cited by its own code's clause
        both = 'Anoscopy was performed today, and rubber band ligation x3 was completed.'
        self.assertEqual(self.unproposed(both, ('46600', 'Anoscopy was performed today'),
                                         ('46221', 'rubber band ligation x3 was completed')).status, 'pass')
        # one procedure's sentence cited by one of its clauses, with or without the name
        for clause in ('Anoscopy was performed today', 'was performed today with a disposable anoscope'):
            with self.subTest(clause=clause):
                self.assertEqual(self.unproposed('Anoscopy was performed today with a disposable anoscope.',
                                                 ('46600', clause)).status, 'pass')
        # a passage across two procedures' lines still covers neither
        check = self.unproposed('Anoscopy was performed today.\nRubber band ligation x3 completed today.',
                                ('46600', 'Anoscopy was performed today.\nRubber band ligation x3 completed today.'))
        self.assertEqual(check.status, 'warn')
        self.assertIn('“Anoscopy” and “Rubber band ligation x3”', check.detail)


# --- validation:9: services.unproposed's coverage is indexed once per assessment --------------------------------------

def assess_timed(text, *picks):
    """Real routing outside the clock; (seconds assess() took, result). picks: (code, [(start, end)])."""
    import json
    import time
    from datetime import date
    from studio.gi.context import extract_context
    from studio.gi.detect import route
    from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, RoutingResult, from_jsonable,
                              to_jsonable)
    from studio.validation.engine import assess
    from tests.test_repairs_r3_validation_b import REFERENCE
    day = date(2026, 10, 21)
    routing = from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, day)))))
    codes = tuple(ProviderCode('selected', 'cpt', code, 'UNVERIFIED',
                               tuple(EvidenceSpan(0, s, e, text[s:e], True) for s, e in spans), index=index)
                  for index, (code, spans) in enumerate(picks))
    started = time.perf_counter()
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text), routing=routing,
                    normalized=NormalizedResponse('corti', 'corti-coding@1', codes=codes), reference=REFERENCE,
                    service_date=day, provider_status='succeeded', extraction_status='ok')
    return time.perf_counter() - started, result


class CoverageCostTests(Case):
    """validation:9 (high, new defect from 8b4a17862). Coverage scanned every evidence span of every gi.other selection
    for every routed mention: 6,000 done mentions and 26,000 one-word spans took 61 s in assess() (9 s at R3B-BASE).
    It is indexed once per assessment now."""

    def test_many_mentions_and_many_spans_assess_in_bounded_time(self):
        # Under Assessment the one-word passages read silent; under an MDM heading each reads performed by its
        # section, so each is also read for the code's own procedure (engine._unnamed_other, round 4 validation:9's
        # sibling loops: past 120 s at the start commit).
        lines, words = 8000, 10000
        for heading in ('Assessment: ', 'Medical decision making: '):
            with self.subTest(heading=heading):
                text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                        + 'Anoscopy was performed today.\n' * lines + heading + ' '.join(['stable'] * words)
                        + '.\nTotal time: 32 minutes.\n')
                first = text.index(heading) + len(heading)
                visit = text.index(VISIT)
                elapsed, result = assess_timed(text, ('99213', [(visit, visit + len(VISIT))]),
                                               ('91010', [(first + 7 * n, first + 7 * n + 6) for n in range(words)]))
                self.assertLess(elapsed, 10.0)  # 25 s or more scanning per mention or per passage; about 3.5 s now
                unproposed = next(c for c in result.encounter_checks if c.id == 'services.unproposed')
                self.assertIn('Possible missed service: Other GI service (“Anoscopy”)', unproposed.detail)


# --- validation:2, validation:3, evidence:0, release:11: a gi.other code needs its own procedure named as done -----

FOLLOW_UP = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
             'Chief complaint: follow-up after hemorrhoid banding.\nFindings: {line}\nMedical decision making: moderate.\n'
             'Total time: 32 minutes.\n')
OFFICE_DECLINED = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                   'Chief complaint: rectal bleeding.\n{body}\nMedical decision making: moderate.\n'
                   'Total time: 32 minutes.\n')
DECLINED = 'Procedure: Anoscopy - patient declined.'
COLONOSCOPY = (HEAD + 'Procedure: Colonoscopy\nIndication: Average-risk screening.\nFindings: The colonoscope was '
               'advanced to the cecum. The colon was normal. {line}\nImpression: Normal colonoscopy.\n'
               'Plan: Repeat colonoscopy in 10 years.\n')
CECUM = 'The colonoscope was advanced to the cecum.'


class OwnProcedureNamedTests(Case):
    """validation:2, validation:3, evidence:0 and release:11 (critical, under-corrections of round 3 validation:0). A
    gi.other code was ready from a passage read performed only by its section (or as the office visit's own
    documentation) whenever its sentence opened with any procedure word or held an act participle: a healed banding
    site, a prior or future banding, a hemorrhoidectomy scar, a declined or deferred banding, the visit statement
    worded with "was performed", or another procedure's findings. Such a passage now counts only when a routed gi.other
    mention read as done lies in it, an explicit act is stated today, or it is the first sentence of a procedure section
    whose routed mention is read as done - and the procedure that counts must be the code's own (by the gi.other
    number ranges). Anything else holds (section_only), never excludes."""

    def assertSectionOnly(self, item, passage):
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'),
                         [c.detail for c in item.checks])
        self.assertIn('performed_status', [c.fact for c in item.clarifications])
        status = check_of(item, 'service.status')
        self.assertEqual(status.status, 'warn')
        self.assertNotIn('Documented as performed', status.detail)
        self.assertIn(f'“{passage}”', status.detail)
        self.assertIn('names no procedure', status.detail)

    def test_validation2_a_follow_up_finding_names_no_banding_done(self):
        for line, code in (('Banding sites well healed.', '46221'),
                           ('The hemorrhoids that were banded at the first session have resolved.', '46221'),
                           ('The internal hemorrhoids we banded have resolved.', '46221'),
                           ('Ligation sites are healed.', '46221'),
                           ('Post-banding ulcer at the right posterior column, healing.', '46221'),
                           ('Hemorrhoidectomy scar noted.', '46221'), ('Hemorrhoidectomy scar noted.', '46250'),
                           # each guard of the stated act on its own: another time no routing cue reads (no today),
                           # a relative clause that says today, "we" after the sentence's own subject
                           ('Internal hemorrhoids were banded at the first session.', '46221'),
                           ('The hemorrhoid that was banded at her first session bled again today.', '46221'),
                           ('The hemorrhoids we banded at the first session bled again today.', '46221')):
            with self.subTest(line=line, code=code):
                proposals, _ = real(FOLLOW_UP.format(line=line), (code, line))
                self.assertSectionOnly(proposals[code], line)

    def test_validation2_a_procedure_line_that_is_not_done(self):
        for body, line in (('Procedure: Rubber band ligation, patient prefers to wait.',
                            'Rubber band ligation, patient prefers to wait.'),
                           ('Procedure: Rubber band ligation offered.', 'Rubber band ligation offered.'),
                           ('Procedure: Rubber band ligation candidate.', 'Rubber band ligation candidate.'),
                           (f'{DECLINED}\nBanding candidate.', 'Banding candidate.'),
                           (f'{DECLINED}\nHemorrhoid banding candidate.', 'Hemorrhoid banding candidate.')):
            with self.subTest(line=line):
                proposals, _ = real(OFFICE_DECLINED.format(body=body), ('46221', line))
                self.assertSectionOnly(proposals['46221'], line)

    def test_validation3_a_visit_statement_worded_as_performed_names_no_procedure(self):
        for visit in ('Established patient office visit was performed today.',
                      'An established patient office visit was completed today.', 'Office visit performed today.',
                      'Telehealth video visit was completed.'):
            text = (HEAD + f'Place of service: Office (POS 11)\n{visit}\nChief complaint: rectal bleeding.\n{DECLINED}\n'
                    'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
            for code in ('46221', '46600'):
                with self.subTest(visit=visit, code=code):
                    proposals, _ = real(text, ('99213', 'Total time: 32 minutes.'), (code, visit))
                    self.assertSectionOnly(proposals[code], visit)
                    self.assertIn('only as E/M documentation', check_of(proposals[code], 'service.status').detail)
                    self.assertVisitHeld(proposals, f'the service reported as {code} is possibly performed', '99213')

    def test_evidence0_a_prior_future_or_descriptive_findings_line(self):
        for line, code in (('S/p hemorrhoid banding.', '46221'), ('History of hemorrhoid banding.', '46221'),
                           ('Prior hemorrhoid banding sites were well healed.', '46221'),
                           ('Previous rubber band ligation sites appeared well healed.', '46221'),
                           ('Hemorrhoid banding at a later date.', '46221'),
                           ('Banding candidate: grade 2 internal hemorrhoids.', '46221'),
                           ('Hemorrhoidectomy scar noted.', '46250'), ('Post-hemorrhoidectomy changes were seen.', '46250'),
                           ('Prior anoscopy showed grade 2 internal hemorrhoids.', '46600'),
                           ('Anoscopy findings from her referral were reviewed.', '46600')):
            with self.subTest(line=line):
                proposals, _ = real(COLONOSCOPY.format(line=line), ('45378', CECUM), (code, line))
                self.assertReady(proposals['45378'])
                self.assertSectionOnly(proposals[code], line)

    def test_evidence0_a_historical_procedure_line_in_an_office_note(self):
        for line in ('Prior hemorrhoid banding.', 'History of hemorrhoid banding.', 'S/p hemorrhoid banding.'):
            with self.subTest(line=line):
                proposals, _ = real(OFFICE_DECLINED.format(body=f'Procedure: {line}'), ('46221', line))
                self.assertSectionOnly(proposals['46221'], line)

    def test_release11_another_procedure_s_passage_is_not_the_code_s(self):
        report = (HEAD + 'Procedure: Anoscopy\nFindings: Anoscopy showed grade 3 internal hemorrhoids. Banding was '
                  'deferred because she takes apixaban.\n')
        line = 'Anoscopy showed grade 3 internal hemorrhoids.'
        proposals, _ = real(report, ('46600', line), ('46221', line))
        self.assertSectionOnly(proposals['46221'], line)
        proposals, _ = real(report, ('46221', 'Anoscopy\nFindings'))  # the routed anoscopy itself
        self.assertEqual(proposals['46221'].status, 'needs_clarification')
        for body, cited, code in (
                ('Procedure: Anoscopy\nFindings: On anoscopy, there were grade 3 internal hemorrhoids. The patient '
                 'declined banding.', 'On anoscopy, there were grade 3 internal hemorrhoids.', '46221'),
                ('Procedure: Anoscopy\nFindings: Anoscopy revealed grade 3 internal hemorrhoids.\nPlan: Rubber band '
                 'ligation at the next visit.', 'Anoscopy revealed grade 3 internal hemorrhoids.', '46221'),
                ('Procedure: Anoscopy\nFindings: Anoscopy showed a small anal fissure.',
                 'Anoscopy showed a small anal fissure.', '45300'),
                ('Procedure: Anal dilation.\nFindings: Stricture.', 'Anal dilation.', '43450'),  # not the esophagus
                ('Procedure: Gastrostomy tube replacement.\nFindings: Done.', 'Gastrostomy tube replacement.',
                 '43760')):  # a range that lists no procedure: never named by a section alone
            with self.subTest(cited=cited, code=code):
                proposals, _ = real(HEAD + body + '\n', (code, cited))
                self.assertSectionOnly(proposals[code], cited)
        # another act stated today, and a banding in a colonoscopy's own text, are not the code's
        line = 'The hemorrhoid was cauterized today.'
        proposals, _ = real(OFFICE_DECLINED.format(body=f'{DECLINED}\n{line}'), ('46221', line))
        self.assertSectionOnly(proposals['46221'], line)
        line = 'Internal hemorrhoids were banded today with the colonoscope in retroflexion.'
        proposals, _ = real(COLONOSCOPY.format(line=line), ('45378', CECUM), ('46221', line))
        self.assertSectionOnly(proposals['46221'], line)

    def test_controls_the_code_s_own_procedure_named_as_done_stays_ready(self):
        report = HEAD + 'Procedure: Anoscopy with rubber band ligation of two internal hemorrhoids.\nFindings: Grade 2.\n'
        boxes = (HEAD + 'Procedure: ☒ Informed consent ☒ Rubber band ligation of two columns\n'
                 'Findings: Grade 2 internal hemorrhoids.\n')
        cases = (
            # a routed gi.other mention read as done, the code's own, lies in the passage (procedure reports)
            (report, 'Anoscopy with rubber band ligation of two internal hemorrhoids.', '46221'),
            (report, 'Anoscopy with rubber band ligation of two internal hemorrhoids.', '46600'),
            (boxes, '☒ Informed consent ☒ Rubber band ligation of two columns', '46221'),
            (HEAD + 'Procedure: Anoscopy\nFindings: Grade 2.\n', 'Anoscopy', '46600'),
            # routing's stated-act mention, read done by its findings section (no E/M documented)
            (HEAD + 'Procedure: Anoscopy\nFindings: Internal hemorrhoids were banded x3.\n',
             'Internal hemorrhoids were banded x3.', '46221'),
            (HEAD + 'Procedure: Esophageal dilation with a 54 Fr bougie.\nFindings: Stricture.\n',
             'Esophageal dilation with a 54 Fr bougie.', '43450'),
            (HEAD + 'Procedure: Rigid proctosigmoidoscopy.\nFindings: Normal.\n', 'Rigid proctosigmoidoscopy.', '45300'),
            (HEAD + 'Procedure: Liver biopsy.\nFindings: Two cores.\n', 'Liver biopsy.', '47000'),
            (HEAD + 'Procedure: Paracentesis.\nFindings: 3 L removed.\n', 'Paracentesis.', '49082'),
            # the first sentence of a procedure section whose routed mention, the code's own, is read as done
            (HEAD + 'Procedure: Rubber band ligation, three columns.\nFindings: Grade 2.\n', 'three columns', '46221'),
            # an explicit act stated today (office notes)
            (OFFICE_DECLINED.format(body=f'{DECLINED}\nInternal hemorrhoids were banded x3 today.'),
             'Internal hemorrhoids were banded x3 today.', '46221'),
            (OFFICE_DECLINED.format(body=f'{DECLINED}\nTwo internal hemorrhoids were banded today without '
                                         'complication.'),
             'Two internal hemorrhoids were banded today without complication.', '46221'),
            (OFFICE_DECLINED.format(body=f'{DECLINED}\nToday we banded two internal hemorrhoids.'),
             'Today we banded two internal hemorrhoids.', '46221'),
            (OFFICE_DECLINED.format(body=f'{DECLINED}\nInternal hemorrhoids were banded x3 today.'),
             'Internal hemorrhoids', '46221'),
            # an explicit performance cue is not a section-only reading (unchanged)
            (OFFICE_DECLINED.format(body=f'{DECLINED}\nRubber band ligation x3 completed today.'),
             'Rubber band ligation x3 completed today.', '46221'),
        )
        for text, passage, code in cases:
            with self.subTest(passage=passage, code=code):
                proposals, _ = real(text, (code, passage))
                self.assertReady(proposals[code])
                self.assertEqual(check_of(proposals[code], 'service.status').status, 'pass')


# --- release:7 and evidence:5: routing's own holds in plan, history and indication sections hold the E/M ------------

NOT_TODAY_NOTE = (HEAD + 'Place of service: Office (POS 11)\n{visit}\n{body}\n'
                  'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
STATED = 'Two internal hemorrhoids were banded today without complication.'
AN_HOUR_AGO = 'Rubber band ligation of two internal hemorrhoids was performed an hour ago.'


class NotTodayRoutingHoldsTests(Case):
    """release:7 (critical, under-correction of routing:22). Routing holds a procedure stated by its act or its findings
    with no performance cue (OTHER_STATED), or by a time that may place it on another date (ANOTHER_TIME), but in a
    plan, history or indication section validation counted only routing's PLAN_TODAY hold. Free text after a "Chief
    complaint:" line is that line's indication section, so the office E/M selected alone was ready beside a banding
    done today. Those two holds now count there too, as PLAN_TODAY does; hedges and plain section defaults do not."""

    def assertHeldBeside(self, visit, body):
        proposals, _ = real(NOT_TODAY_NOTE.format(visit=visit, body=body), ('99214', visit))
        self.assertVisitHeld(proposals, f'{OTHER_LABEL} is possibly performed on the same date')

    def test_a_stated_act_after_the_chief_complaint_holds_the_visit(self):
        for body in (f'Chief complaint: Rectal bleeding.\n{STATED}', f'Chief complaint: Rectal bleeding.\n\n{STATED}',
                     f'Chief complaint: Rectal bleeding. {STATED}', f'Chief complaint\nRectal bleeding.\n{STATED}',
                     f'Reason for visit: Rectal bleeding.\n{STATED}',
                     'Chief complaint: Rectal bleeding.\nToday we banded two internal hemorrhoids.',
                     'Chief complaint: Rectal bleeding.\nTwo internal hemorrhoids were banded x3 today.'):
            with self.subTest(body=body):
                self.assertHeldBeside(VISIT, body)

    def test_the_round_3_claimant_s_own_layout_holds_the_visit(self):
        visit = 'Established patient office visit for rectal bleeding.'
        for line in ('Two internal hemorrhoids were banded today.', 'Anoscopy: grade 2 internal hemorrhoids, no fissure.',
                     'Today we banded two internal hemorrhoids.', 'Internal hemorrhoids were banded x3 today.',
                     'A perianal abscess was incised and drained today.'):
            with self.subTest(line=line):
                self.assertHeldBeside(visit, f'Chief complaint: rectal bleeding.\n{line}')

    def test_another_time_in_an_indication_history_or_plan_section_holds_the_visit(self):
        for heading in ('Chief complaint: Rectal bleeding.\n', 'History of present illness: ', 'Plan: '):
            with self.subTest(heading=heading):
                self.assertHeldBeside(VISIT, heading + AN_HOUR_AGO)

    def test_controls_hedges_and_section_defaults_stay_released(self):
        for body in ('Chief complaint: Rectal bleeding.\nPlan: Possible banding if bleeding persists.',
                     'Chief complaint: Rectal bleeding.\nPlan: Rubber band ligation next week.',
                     'History of present illness: Colonoscopy in 2019 was normal.',
                     'Plan: Possible EGD if symptoms persist.'):
            with self.subTest(body=body):
                proposals, _ = real(NOT_TODAY_NOTE.format(visit=VISIT, body=body), ('99214', VISIT))
                self.assertVisitReady(proposals)


class PlanTodayRealRoutingTests(Case):
    """evidence:5 (medium, false green). round 3b's E/M-alone hold through routing's PLAN_TODAY cue was pinned only by
    constructed readings and by a contract test with a getattr default: rewording the cue routing emits kept every test
    green while the E/M selected alone became ready. These route for real and read the cue routing emits."""

    CASES = (('EGD this morning revealed a Schatzki ring, dilated to 18 mm.', 'gi.egd'),
             ('EGD today showed esophagitis; biopsies taken.', 'gi.egd'),
             ('Colonoscopy today: two polyps removed with cold snare.', 'gi.colonoscopy'))

    def test_the_e_m_selected_alone_is_held_by_routing_s_plan_today_cue(self):
        from datetime import date
        from studio.gi.detect import route
        from studio.validation import checks
        from tests.test_repairs_r3_time import PLAN_HEADINGS, TIME, plan_office
        for heading in PLAN_HEADINGS[:3]:
            for sentence, family in self.CASES:
                with self.subTest(heading=heading, sentence=sentence):
                    text = plan_office(sentence + ' Start omeprazole.', heading)
                    mention = next(m for m in route(text, date(2026, 10, 21)).finding(family).mentions
                                   if m.section == 'plan')
                    self.assertIn(checks.PLAN_TODAY_CUE, mention.cues)
                    proposals, _ = real(text, ('99213', TIME))
                    self.assertVisitHeld(proposals, f'{PROFILES[family].label} is possibly performed', '99213')

    def test_the_e_m_citing_its_own_plan_today_is_ready(self):
        from tests.test_repairs_r3_time import plan_office
        text = plan_office('Start omeprazole 40 mg today.')
        proposals, _ = real(text, ('99213', 'Start omeprazole 40 mg today.'))
        self.assertVisitReady(proposals, '99213')

    def test_the_cues_validation_reads_are_routing_s(self):
        from studio.gi import detect
        from studio.validation import checks
        self.assertEqual(detect.PLAN_TODAY, checks.PLAN_TODAY_CUE)
        self.assertTrue(detect.OTHER_STATED.startswith(checks._VAL_OTHER_STATED_CUE))
        self.assertEqual(detect.ANOTHER_TIME_PREFIX, checks._VAL_ANOTHER_TIME_CUE)


# --- validation:6: an E/M is never excluded by a negative reading about other services ------------------------------

def rowan_assessment():
    """The retained real Corti response for the Rowan note (tests/fixtures/corti), its context-0 evidence re-bound from
    the CRLF source to the canonical text (every move asserted), normalized by the real adapter, with real routing
    (JSON round trip) and the member's service date, as the pipeline would assess it."""
    import json
    import tempfile
    from datetime import date
    from pathlib import Path
    from studio.gi.context import extract_context, merge_user_values
    from studio.gi.detect import route
    from studio.ingest.text import canonicalize
    from studio.providers import CortiProvider
    from studio.types import PageSpan, RoutingResult, from_jsonable, to_jsonable
    from studio.validation.engine import assess
    from tests.test_repairs_r3_validation_b import REFERENCE
    fixtures = Path(__file__).resolve().parent / 'fixtures' / 'corti'
    source = (fixtures / 'rowan.source.txt').read_bytes().decode()
    text = canonicalize(source)
    raw = json.loads((fixtures / 'rowan.response.raw.json').read_bytes())
    for key in ('codes', 'candidates'):
        for item in raw[key]:
            for group in [item] + list(item.get('alternatives', [])):
                for span in group.get('evidences', []):
                    if span['contextIndex'] != 0:
                        continue
                    start, end = span['start'], span['end']
                    assert source[start:end] == span['text']
                    start, end = start - source[:start].count('\r'), end - source[:end].count('\r')
                    assert text[start:end] == span['text'].replace('\r\n', '\n')
                    span.update(start=start, end=end, text=text[start:end])
    day = date(2026, 10, 16)
    with tempfile.TemporaryDirectory() as folder:
        provider = CortiProvider(Path(folder) / 'never-read.env')
        normalized = provider.normalize(provider.build_request(text, day), json.dumps(raw).encode())
    assert normalized.problems == ()
    routing = from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, day)))))
    context = merge_user_values(extract_context(text), {'service_date': '2026-10-16'})
    return text, assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=context, routing=routing,
                        normalized=normalized, reference=REFERENCE, service_date=day, provider_status='succeeded',
                        extraction_status='ok')


class EmNegativeAboutOtherServicesTests(Case):
    """validation:6 (critical, under-correction of round 3 validation:3). The retained real Corti response's 99213
    cites "No laboratory testing, imaging, endoscopy or other procedure was performed at this encounter." (negated, about
    other services, overlapping routing's negated gi.other mention) and "Further testing will be considered after review
    of the prior records; no procedure has been ordered or performed today." (historical: the records cue). 99213 was
    excluded "Documented as negated", and services.unproposed warned of a possible missed E/M although 99213 was
    selected. A negative reading of an E/M's passage that touches no routed E/M mention and names another service now
    holds the E/M (hold-only: never silent, never an exclusion). A cue that plans, dates or denies the visit itself
    keeps excluding."""

    def test_the_retained_rowan_response_does_not_exclude_the_visit(self):
        from tests.test_repairs_r3_validation_b import encounter_check
        _, result = rowan_assessment()
        visit = next(p for p in result.proposals if p.code == '99213')
        self.assertEqual((visit.bucket, visit.status), ('selected', 'needs_clarification'), visit.exclusion_reason)
        self.assertFalse(visit.reinstatable)
        status = check_of(visit, 'service.status')
        self.assertNotIn('Documented as negated', status.detail)
        self.assertNotIn('Documented as historical', status.detail)
        unproposed = encounter_check(result, 'services.unproposed')
        self.assertNotIn('Office / outpatient evaluation and management', unproposed.detail)

    def test_each_channel_alone_holds_rather_than_excludes(self):
        text, _ = rowan_assessment()
        for passage in ('No laboratory testing, imaging, endoscopy or other procedure was performed at this encounter.',
                        'Further testing will be considered after review of the prior records; no procedure has been '
                        'ordered or performed today.'):
            with self.subTest(passage=passage):
                proposals, _ = real(text.replace('Date of service: 16 October 2026', 'Date of service: 2026-10-16'),
                                    ('99213', passage))
                self.assertEqual((proposals['99213'].bucket, proposals['99213'].status),
                                 ('selected', 'needs_clarification'))

    def test_controls_a_cue_about_the_visit_still_excludes(self):
        from tests.test_repairs_status_r2_validation import ASSESSMENT_AND_PLAN
        text = ASSESSMENT_AND_PLAN.format(plan='Discussed colonoscopy; the patient will think about it. '
                                               'Return in three months.')
        proposals, _ = real(text, ('99214', 'Return in three months.'))
        self.assertEqual((proposals['99214'].bucket, proposals['99214'].reinstatable), ('excluded', True))
        from tests.test_repairs_r3_validation_b3 import V3
        for line in ('Return office visit is scheduled for 2026-12-01.', 'Follow-up office visit.'):
            with self.subTest(line=line):
                proposals, _ = real(V3.format(extra=f'{line}\n'), ('99213', line))
                self.assertEqual((proposals['99213'].bucket, proposals['99213'].reinstatable), ('excluded', True))


# --- validation:8: services.unsupported names an excluded, reinstatable code outside the profiles --------------------

class UnsupportedExcludedTests(Case):
    """validation:8 (high). services.unsupported skipped a selection outside the GI profiles that its status reading
    excluded (reinstatable), so it printed "No selected code or detected service falls outside the GI profiles" beside a
    selected 46221 - and kept printing it after a reviewer reinstated and approved that code. Such a selection is now
    listed in a third group, never called performed, and the none-line is never printed while one exists."""

    def test_an_excluded_reinstatable_code_outside_the_profiles_is_listed(self):
        from studio.validation import checks
        from tests.test_repairs_r3_validation_b import encounter_check
        for plan, code in (('Plan: Rubber band ligation of the internal hemorrhoids.', '46221'),
                           ('Plan: Rubber band ligation of an internal hemorrhoid is scheduled for 2026-11-03.', '46221'),
                           ('Plan: Barium enema next week.', '74270')):
            with self.subTest(code=code, plan=plan):
                passage = plan[len('Plan: '):]
                proposals, result = real(OFFICE.format(line=plan), ('99213', VISIT), (code, passage))
                self.assertEqual((proposals[code].bucket, proposals[code].reinstatable), ('excluded', True))
                unsupported = encounter_check(result, 'services.unsupported')
                self.assertEqual(unsupported.status, 'warn')
                self.assertNotEqual(unsupported.detail, checks.UNSUPPORTED_NONE)
                self.assertIn(f'({code})', unsupported.detail)
                self.assertIn('excluded', unsupported.detail)
                self.assertNotIn('Performed without a GI profile', unsupported.detail)
                self.assertIn(code, [c for entry in result.unsupported for c in entry['codes']])

    def test_controls_performed_and_held_wordings_are_unchanged(self):
        from studio.validation import checks
        performed = checks.unsupported_check([{'family': 'gi.other', 'label': 'Other GI service', 'status': 'performed',
                                               'detail': '', 'codes': ['46221']}])
        self.assertEqual(performed.detail, 'Performed without a GI profile in this release: Other GI service. Review '
                                           'required.')
        held = checks.unsupported_check([{'family': 'gi.other', 'label': 'Other GI service', 'status': 'uncertain',
                                          'detail': '', 'codes': ['46221']}])
        self.assertEqual(held.detail, 'Selected without a GI profile in this release, not established as performed: '
                                      'Other GI service (46221). Review required.')
        self.assertEqual(checks.unsupported_check([]).detail, checks.UNSUPPORTED_NONE)
