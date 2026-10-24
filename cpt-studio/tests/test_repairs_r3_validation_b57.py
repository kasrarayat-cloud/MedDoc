"""Regressions for refutation round 3, validation:5 and validation:7: gi.other procedures read mention by mention
for coverage and for the same-day E/M hold. Real routing, the real span reader and the engine; synthetic text only.
"""
from studio.reference.store import InMemoryReferenceLookup
from studio.validation import checks
from tests.test_repairs_r3_validation_b import (HEAD, REFERENCE, ROWS, VISIT, Case, check_of, encounter_check,
                                                 real)
from tests.test_repairs_status_r2_validation import placed
from tests.test_validation import EM, MUE_INFO, PFS_INFO, EngineCase, Note, finding, selected, visit_context

TIME = 'Total time: 32 minutes.'


# --- validation:5: one gi.other code never covers another gi.other procedure --------------------------------------

V5 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit for rectal bleeding.\n{first}\n'
      'Rubber band ligation x3 completed today.\nMedical decision making: moderate.\nTotal time: 32 minutes.\n')
BANDING = 'Rubber band ligation x3 completed today.'


class Validation5OtherMentionCoverageTests(Case):
    """validation:5 — a performed gi.other procedure is covered only by a selected, non-excluded gi.other code whose
    exact evidence lies in that procedure's sentence; otherwise it is a possible missed service."""

    def test_a_banding_beside_a_selected_anoscopy_or_manometry_is_named_as_possibly_missed(self):
        for first, code in (('Anoscopy was performed today.', '46600'),
                            ('Esophageal manometry was performed today.', '91010')):
            with self.subTest(code=code):
                _, result = real(V5.format(first=first), ('99213', TIME), (code, first))
                unproposed = encounter_check(result, 'services.unproposed')
                self.assertEqual(unproposed.status, 'warn')
                self.assertIn('Possible missed service: Other GI service (“Rubber band ligation x3”)',
                              unproposed.detail)

    def test_controls_every_procedure_cited_by_its_own_code_passes(self):
        first = 'Anoscopy was performed today.'
        _, result = real(V5.format(first=first), ('99213', TIME), ('46600', first), ('46221', BANDING))
        unproposed = encounter_check(result, 'services.unproposed')
        self.assertEqual((unproposed.status, unproposed.detail), ('pass', checks.UNPROPOSED_PASS))

    def test_controls_with_no_gi_other_code_the_family_is_named_as_before(self):
        _, result = real(V5.format(first='Anoscopy was performed today.'), ('99213', TIME))
        self.assertEqual(encounter_check(result, 'services.unproposed').detail,
                         'Possible missed service: Other GI service is documented as performed with no selected '
                         'proposal.')

    def test_a_passage_with_its_line_breaks_still_lies_in_its_sentence(self):
        first = 'Anoscopy was performed today.'
        for evidence in (f'{BANDING}\n', f'\n{BANDING}'):
            with self.subTest(evidence=evidence):
                _, result = real(V5.format(first=first), ('99213', TIME), ('46600', first), ('46221', evidence))
                self.assertEqual(encounter_check(result, 'services.unproposed').status, 'pass')

    def test_one_passage_across_both_procedures_covers_neither(self):
        first = 'Anoscopy was performed today.'
        _, result = real(V5.format(first=first), ('99213', TIME), ('46600', f'{first}\n{BANDING}'))
        self.assertIn('Possible missed service: Other GI service',
                      encounter_check(result, 'services.unproposed').detail)




# --- validation:7: a same-day test whose selected code is XXX does not hold the E/M ------------------------------

V7 = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n{line}\n'
      'Medical decision making: moderate.\nTotal time: 32 minutes.\n')
MANOMETRY = 'Esophageal manometry was performed today.'


class Validation7XxxTestTests(Case):
    """validation:7 — a routed gi.other mention is discounted for the same-day E/M hold only when a selected,
    non-excluded gi.other code with a CMS global period of XXX has exact evidence over the mention's name, and the
    name holds one procedure. Everything else stays fail-closed."""

    def test_a_diagnostic_test_coded_xxx_does_not_hold_the_visit(self):
        for line, code in ((MANOMETRY, '91010'), ('Capsule endoscopy was performed today.', '91110'),
                           ('Anorectal manometry was performed today.', '91122')):
            with self.subTest(code=code):
                proposals, result = real(V7.format(line=line), ('99213', VISIT), (code, line))
                self.assertVisitReady(proposals, '99213')
                self.assertReady(proposals[code])
                self.assertIsNotNone(check_of(proposals['99213'], 'em.same_day_coverage'))

    def test_controls_the_visit_stays_held(self):
        two = 'Esophageal manometry and esophageal dilation were performed today.'
        no_xxx = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {PFS_INFO.key: {
            key: row for key, row in ROWS.items() if key[0] != '91010'}, MUE_INFO.key: {}})
        cases = (
            ('not selected', V7.format(line=MANOMETRY), (('99213', VISIT),), REFERENCE),
            ('two procedures in one name', V7.format(line=two), (('99213', VISIT), ('91010', two)), REFERENCE),
            ('no fee-schedule row', V7.format(line=MANOMETRY), (('99213', VISIT), ('91010', MANOMETRY)), no_xxx),
            ('evidence beside the name', V7.format(line=MANOMETRY),
             (('99213', VISIT), ('91010', 'was performed today.')), REFERENCE),
            ('a procedure with a global period', V7.format(line=BANDING), (('99213', VISIT), ('46221', BANDING)),
             REFERENCE),
            ('an E/M passage over the name', V7.format(line=MANOMETRY), (('99213', VISIT, MANOMETRY),), REFERENCE),
            ('evidence over part of the name', V7.format(line=MANOMETRY),
             (('99213', VISIT), ('91010', 'manometry was performed today.')), REFERENCE),
        )
        for name, text, picks, reference in cases:
            with self.subTest(name):
                proposals, _ = real(text, *picks, reference=reference)
                self.assertEqual(proposals['99213'].status, 'needs_clarification')
                self.assertIn('separate_em', [c.fact for c in proposals['99213'].clarifications])
                # the routed procedure itself is counted, not only a selected code
                self.assertIn('Other GI service', check_of(proposals['99213'], 'em.same_day_procedure').detail)

    def test_controls_an_xxx_test_beside_an_uncoded_banding_still_holds(self):
        text = V7.format(line=f'{MANOMETRY}\n{BANDING}')
        proposals, _ = real(text, ('99213', VISIT), ('91010', MANOMETRY))
        self.assertVisitHeld(proposals, 'Other GI service is documented as performed', '99213')



class Validation57EngineTests(EngineCase):
    """validation:5 and validation:7 at the engine, with routing's readings stated explicitly."""

    NOTE = Note('Date of service: 2026-10-21', 'Office visit: established patient seen for dysphagia.',
                'Total time 32 minutes.', 'Esophageal manometry was performed today.',
                'Rubber band ligation x3 completed today.')
    VISIT, TIME = 'Office visit: established patient seen for dysphagia.', 'Total time 32 minutes.'
    MANOMETRY, BAND = 'Esophageal manometry was performed today.', 'Rubber band ligation x3 completed today.'

    def run_case(self, *codes, mentions, statuses=None):
        self.statuses = {self.TIME: None, **(statuses or {})}
        visit = finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                        facts={'em_basis': 'total time 32 minutes'})
        other = finding('gi.other', 'performed', *mentions)
        return self.run_engine(self.NOTE, selected('99213', self.NOTE.span(self.TIME)), *codes,
                               findings=[visit, other], ctx=visit_context(), reference=REFERENCE)

    def mention(self, phrase, status='performed', section='other', *cues):
        return placed(self.NOTE, 'gi.other', status, phrase, section, *(cues or ('performed: was performed',)))

    def test_only_a_selected_non_excluded_xxx_code_discounts_its_test(self):
        done = ('performed', ('performed: was performed',))
        cases = (('selected', done, 'ready'), ('excluded', ('negated', ('negated: declined',)), 'needs_clarification'),
                 ('held', ('uncertain', ('uncertain: Possible',)), 'ready'))
        for name, reading, expected in cases:
            with self.subTest(name):
                result = self.run_case(selected('91010', self.NOTE.span(self.MANOMETRY)),
                                       mentions=(self.mention(self.MANOMETRY),), statuses={self.MANOMETRY: reading})
                self.assertEqual(self.proposal(result, '99213').status, expected)

    def test_an_uncertain_test_that_its_code_describes_is_not_possibly_a_procedure(self):
        hedged = self.mention(self.MANOMETRY, 'uncertain', 'other', 'uncertain: Possible')
        statuses = {self.MANOMETRY: ('performed', ('performed: was performed',))}
        result = self.run_case(selected('91010', self.NOTE.span(self.MANOMETRY)), mentions=(hedged,),
                               statuses=statuses)
        self.assertEqual(self.proposal(result, '99213').status, 'ready')
        visit = self.proposal(self.run_case(mentions=(hedged,)), '99213')
        self.assertIn('Other GI service is possibly performed', self.check(visit, 'em.same_day_procedure').detail)

    def test_only_a_selected_gi_other_code_covers_a_procedure(self):
        """The banding sentence cited by an excluded gi.other code, or by the E/M, is not covered."""
        visit = finding(EM, 'performed', placed(self.NOTE, EM, 'performed', self.VISIT, 'other', 'seen'),
                        facts={'em_basis': 'total time 32 minutes'})
        other = finding('gi.other', 'performed', self.mention(self.MANOMETRY), self.mention(self.BAND))
        manometry = selected('91010', self.NOTE.span(self.MANOMETRY))
        cases = (('an excluded gi.other code', (selected('99213', self.NOTE.span(self.TIME)), manometry,
                                                selected('46221', self.NOTE.span(self.BAND))), ('negated', ())),
                 ('an E/M passage', (selected('99213', self.NOTE.span(self.TIME), self.NOTE.span(self.BAND)),
                                     manometry), None))
        for name, codes, band in cases:
            with self.subTest(name):
                self.statuses = {self.TIME: None, self.MANOMETRY: ('performed', ('performed: was performed',)),
                                 self.BAND: band}
                result = self.run_engine(self.NOTE, *codes, findings=[visit, other], ctx=visit_context(),
                                         reference=REFERENCE)
                self.assertTrue(all(p.bucket == 'selected' for p in result.proposals if p.code != '46221'))
                unproposed = self.encounter_check(result, 'services.unproposed')
                self.assertEqual(unproposed.status, 'warn')
                self.assertIn('Other GI service (“Rubber band ligation x3 completed today.”)', unproposed.detail)
