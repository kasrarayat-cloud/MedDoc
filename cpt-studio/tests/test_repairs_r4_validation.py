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
        lines, words = 8000, 4000
        text = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                + 'Anoscopy was performed today.\n' * lines + 'Assessment: ' + ' '.join(['stable'] * words)
                + '.\nTotal time: 32 minutes.\n')
        first = text.index('Assessment: ') + len('Assessment: ')
        visit = text.index(VISIT)
        elapsed, result = assess_timed(text, ('99213', [(visit, visit + len(VISIT))]),
                                       ('91010', [(first + 7 * n, first + 7 * n + 6) for n in range(words)]))
        self.assertLess(elapsed, 6.0)  # 11.5 s with the per-mention scan, about 1.6 s indexed
        unproposed = next(c for c in result.encounter_checks if c.id == 'services.unproposed')
        self.assertIn('Possible missed service: Other GI service (“Anoscopy”)', unproposed.detail)
