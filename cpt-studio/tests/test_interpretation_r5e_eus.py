"""DECISIONS D156 (the Gemini migration's round 5e, narrowing only: the round-5d review of the eus4 repair D145,
round5d/results-missing-reviews.json 'review:eus4' problems 0 and 5, and the eus4 builder's disagreement 3),
SYNTHETIC, each built from its source's own input. Nothing is sent.
- (1) the builder's disagreement 3 (pre-existing; a wrong READY against the installed release c2e53f8e): a DONE act of
  the EUS session of a kind its catalogue entry does not list, whose KIND is not usable (the lumen-apposing stent named
  'LAMS', kind words that do not locate), beside its EUS examination, is an act in doubt for D137's rule
  (coverage.eus_unprofiled_doubt), so 43259 is held base_included, as c2e53f8e holds it.
- (2) problem 0 (a dropped genuine question): where no supporting act meets 43240's defining target, 7.4's reading over
  the positive candidates that do not support it but DO meet the target is kept - its question and its 52/53
  consideration - and the target hold's question is asked beside it (events._target_hold).
- (3) problem 5 (wording): an act already reportable is never also recorded as doubted by the relation arm, so a done
  stent beside an UNRESOLVED denial is named once in 43259's base question.
Each test asserts in independent subtests - the outcome, the read-time overlay, the record - so a regression shows every
one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, mapping, wording
from tests.test_interpretation_events import asked, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_integration_d88_d93 import reviewed
from tests.test_interpretation_r4_eus_lower import ready_unheld
from tests.test_interpretation_r5_eus import DRAINAGE_LINES
from tests.test_interpretation_r5c_eus import GB, GE, MASS, examination, gallbladder, with_examination
from tests.test_interpretation_r5d_eus import (DENIED, IN_DOUBT, R6_TARGET, STENT_PLACEMENT, base_held, denial,
                                               entries, related_case, stent)
from tests.test_interpretation_r3_eus import DUODENUM

INCOMPLETE = 'Incomplete procedure: whether modifier 52 or 53 applies'  # wording.incomplete_consideration's opening


# --- (1) a done unlisted act whose kind is not usable -------------------------------------------------------------------

def lams(lines: dict = GE, **changes):
    """The builder's input: problem 2's EUS examination (E1) and the gastroenterostomy's stent (E2), done, its kind words
    'LAMS' - not in the document, so its kind is not usable."""
    return with_examination(lines, stent(kind_words='LAMS', **changes))


LAMS_ATTEMPTED = dict(GE, P4='From the gastric body, deployment of a 20 mm lumen-apposing metal stent into a distended '
                             'jejunal loop was attempted but failed.')
RFA = dict(GE, P1='Procedure: EUS-guided radiofrequency ablation.',
           P4='EUS-guided radiofrequency ablation of the pancreatic head mass was performed.')
OTHER_TIME = dict(GE, P4='At her index EUS on 01/14/2024, a 20 mm lumen-apposing metal stent was deployed from the '
                         'gastric body into a distended jejunal loop.')
NO_STENT = dict(GE, P4='No lumen-apposing metal stent was placed.')
BY_OTHER = dict(GE, P4='From the gastric body, a 20 mm lumen-apposing metal stent was deployed into a distended jejunal '
                       'loop by Dr. Lena Ortiz (fictional) of the advanced endoscopy service.')
CLIP = dict(GE, P4='A hemostatic clip was placed at the puncture site.')
FNA = dict(GE, P1='Procedure: EUS with fine-needle aspiration.',
           P4='EUS-guided fine-needle aspiration of the pancreatic head mass was performed with a 22-gauge needle.')


class AnUnlistedActWhoseKindIsNotUsableIsADoubt(SimpleTestCase):
    """D156 (1): 4f82e5056 and e5628be56 READY 43259 (coding complete_pending_review) beside a done stent whose kind is
    not usable; c2e53f8e holds it [performed_status, target]."""

    def test_d156_43259_beside_a_lams_whose_kind_words_do_not_locate_is_held(self):
        inv, text = lams()
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):  # done, no D137 act (its kind not usable), now in doubt
            event = reading.events['E2']
            self.assertEqual((event['kind']['state'], events.done(event), events.usable(event, 'procedure'),
                              coverage.eus_guided_act(event), coverage.eus_unprofiled_doubt(reading, event)),
                             ('unverified', True, True, False, True))
        result = run(inv, text, [('43259', GE['P2'])])
        with self.subTest(part='assess'):  # 4f82e5056: READY
            base_held(self, result, '43259', (IN_DOUBT,))
        with self.subTest(part='record'):
            self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')),
                             ([], [('E2', 'stent', STENT_PLACEMENT)]))
        with self.subTest(part='completeness'):
            self.assertEqual(result.completeness['state'], 'incomplete')
        with self.subTest(code='43237'):  # 4f82e5056: [extent]
            p = proposal(run(inv, text, [('43237', GE['P2'])]), '43237')
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included', 'extent']))

    def test_d156_the_same_act_begun_and_not_completed_and_an_ablation_are_held(self):
        """The same stent 'attempted but failed', and an EUS-guided ablation whose kind words ('RFA') do not locate."""
        for name, (inv, text), label in (
                ('attempted', lams(LAMS_ATTEMPTED, status='attempted_not_completed',
                                   status_words='was attempted but failed'), IN_DOUBT),
                ('ablation', with_examination(RFA, act('E2', 'P4', 'ablation', 'RFA', status_words='was performed',
                                                       procedure=a('eus', 'EUS-guided', ['P4']),
                                                       target=tg('L1', 'pancreas', 'the pancreatic head mass',
                                                                 ['P4']))), 'ablation (stated in doubt)')):
            with self.subTest(act=name):  # 4f82e5056: READY
                base_held(self, run(inv, text, [('43259', GE['P2'])]), '43259', (label,))

    def test_d156_controls_another_occasion_a_denial_and_another_clinician(self):
        """Unchanged: the LAMS verified at another occasion, denied, or verified as another clinician's is stated here by
        no one - no doubt, 43259 READY as on 4f82e5056 (c2e53f8e holds 43259 on all three)."""
        cases = (('another_occasion', lams(OTHER_TIME, time=a('earlier_encounter', 'At her index EUS on 01/14/2024',
                                                               ['P4']))),
                 ('denied', lams(NO_STENT, status='not_performed', status_words='No lumen-apposing metal stent was placed',
                                 target=tg())),
                 ('another_clinician', inventory(BY_OTHER, events=[examination(), stent(
                     kind_words='LAMS', performer=a('other_clinician', 'Dr. Lena Ortiz (fictional)', ['P4']))],
                     lesions=[MASS], reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')], named=True)))
        for name, (inv, text) in cases:
            reading = events.Reading.of(inv)
            with self.subTest(control=name, part='fixture'):
                self.assertFalse(coverage.eus_unprofiled_doubt(reading, reading.events['E2']))
            with self.subTest(control=name, part='assess'):
                result = run(inv, text, [('43259', GE['P2'])])
                ready_unheld(self, result, '43259')
                self.assertEqual(entries(result, 'doubted'), [])

    def test_d156_controls_a_clip_and_an_act_of_a_listed_kind(self):
        """A hemostatic clip whose kind words do not locate is part of another act (bundled_reason) and never recorded;
        an FNA whose kind words do not locate is a listed kind, coverage.doubted's (unchanged: 43242 held, 43259 held)."""
        clip = act('E2', 'P4', 'clip', 'endoclip', status_words='was placed', procedure=a('eus', 'EUS', ['P1']),
                   target=tg('', 'stomach', 'the puncture site', ['P4']))
        inv, text = with_examination(CLIP, clip)
        with self.subTest(control='clip'):
            result = run(inv, text, [('43259', GE['P2'])])
            ready_unheld(self, result, '43259')
            self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')), ([], []))
        fna = act('E2', 'P4', 'fna', 'FNA-B', status_words='was performed', procedure=a('eus', 'EUS-guided', ['P4']),
                  technique=a('needle', '22-gauge needle', ['P4']),
                  target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P4']))
        inv, text = with_examination(FNA, fna)
        reading = events.Reading.of(inv)
        with self.subTest(control='fna', part='fixture'):
            self.assertFalse(coverage.eus_unprofiled_doubt(reading, reading.events['E2']))
        with self.subTest(control='fna', part='assess'):
            result = run(inv, text, [('43242', FNA['P4']), ('43259', GE['P2'])])
            self.assertEqual([(proposal(result, code).status, asked(proposal(result, code))) for code in ('43242',
                                                                                                         '43259')],
                             [('needs_clarification', ['performed_status']), ('needs_clarification', ['base_included'])])
            # coverage.doubted's own entry (a listed kind whose kind is not usable), as on 4f82e5056; none of D137's
            self.assertEqual(entries(result, 'doubted'), [('E2', 'fna', 'fine-needle aspiration or biopsy')])
            self.assertEqual(coverage.eus_unprofiled_entries(reading, list(reading.events.values()), doubted=True), [])


# --- (2) 7.4's reading over the candidates that meet the target, asked beside the target hold ---------------------------

PSEUDOCYST = les('L1', 'A 9 cm pancreatic pseudocyst', 'P2', landmark='pancreas', site_words='pancreatic',
                 size_words='9 cm')
ATTEMPTED_PFC = 'EUS-guided transmural drainage of the pseudocyst was attempted but failed.'
LATER_PFC = ('Later, EUS-guided transmural drainage of the pseudocyst was performed from the stomach with a 15 mm '
             'lumen-apposing metal stent.')
UNCLEAR_PFC = 'It is unclear whether EUS-guided transmural drainage of the pseudocyst was performed.'
ATTEMPTED = dict(status='attempted_not_completed', status_words='was attempted but failed')
PLACES = {'bile_duct': ('common_bile_duct', 'the common bile duct', 'common bile duct'),
          'gallbladder': ('gallbladder', 'the gallbladder', 'gallbladder')}
ATTEMPTED_Q = ('The drainage of the A 9 cm pancreatic pseudocyst in the pancreas was begun and not completed. Confirm '
               'whether 43240 describes what was done on the date of service.')
ATTEMPTED_REASON = ('The document states the drainage of the A 9 cm pancreatic pseudocyst in the pancreas was begun and '
                    'not completed (“was attempted but failed”). Kept for review: not treated as completed and not '
                    'excluded.')
LATER_Q = ('Was the drainage (stent) of the A 9 cm pancreatic pseudocyst in the pancreas (“was performed”) done at this '
           'encounter?')


def two_drainages(p3: str, pfc_changes: dict, other: str = 'bile_duct', examined: bool = False):
    """The review's input (tools/rv_refute.py two_drainages): an EUS examination (E1), the pseudocyst (L1), a pseudocyst
    drainage in doubt (E2, P3) and a second, done drainage of another structure (E3, P4) - the common bile duct (a
    choledochoduodenostomy) or the gallbladder. ``examined`` (constructed): the examination's own target is the
    pseudocyst, verified, so R6 asks no structure examined."""
    landmark, words, _ = PLACES[other]
    lines = {'P1': 'The linear echoendoscope was advanced to the stomach.',
             'P2': 'A 9 cm pancreatic pseudocyst was seen abutting the posterior gastric wall.',
             'P3': p3, 'P4': DRAINAGE_LINES[other]}
    pfc = dict(status_words='was performed', procedure=a('eus', 'EUS-guided', ['P3']),
               technique=a('stent', 'stent', ['P3']), target=tg('L1', 'pancreas', 'the pseudocyst', ['P3']))
    pfc.update(pfc_changes)
    first = (act('E1', 'P1', 'examination', 'linear echoendoscope', status_words='was advanced',
                 procedure=a('eus', 'echoendoscope', ['P1']), technique=a('endoscope', 'linear echoendoscope', ['P1']),
                 target=tg('L1', 'pancreas', 'A 9 cm pancreatic pseudocyst', ['P2'])) if examined
             else exam('E1', 'P1', words='linear echoendoscope', procedure=a('eus', 'echoendoscope', ['P1'])))
    found = [first, act('E2', 'P3', 'drainage', 'transmural drainage', **pfc),
             act('E3', 'P4', 'drainage', 'transmural drainage', status_words='was performed',
                 procedure=a('eus', 'EUS-guided', ['P4']), technique=a('stent', 'stent', ['P4']),
                 target=tg('', landmark, words, ['P4']))]
    return inventory(lines, events=found, lesions=[PSEUDOCYST], reach=[reached('E1', 'stomach', 'stomach', 'P1')])


def target_question(other: str) -> tuple:
    """(reason, question) of the target hold on the other structure's drainage (E3)."""
    return wording.defining_target_hold('43240', 'drainage', PLACES[other][2], DRAINAGE_LINES[other])


class SevenFourIsAskedBesideTheTargetHold(SimpleTestCase):
    """D156 (2), problem 0 (medium, introduced by D145): 4f82e5056 holds 43240 [target, target] on the review's input,
    asking only which structure the other drainage was done on - the failed pseudocyst drainage in no question and no
    52/53 consideration; e5628be56 asked 7.4's question about it with the consideration ([performed_status, target]);
    c2e53f8e holds [performed_status, target]."""

    def assert_both(self, result, first_q: str, first_reason: str, other: str, facts: list, attempted: bool):
        p = proposal(result, '43240')
        reason, question = target_question(other)
        first = p.clarifications[0]
        self.assertEqual((p.status, p.bucket, asked(p)), ('needs_clarification', 'selected', facts))
        # DECISIONS D161 (1): 7.4's question and the hold's are two clarifications (D156 asked '<7.4's> <the hold's>')
        self.assertEqual((first.question, first.reason), (first_q, first_reason))
        self.assertEqual((p.clarifications[1].fact, p.clarifications[1].question, p.clarifications[1].reason),
                         ('target', question, reason))
        self.assertEqual((p.support['acts'], p.support['question_events']), ([], ['E2', 'E3']))
        self.assertEqual(any(text.startswith(INCOMPLETE) for text in p.modifier_considerations), attempted)
        view = reviewed(result, '43240')
        self.assertEqual((view.status, view.released, [q['question'] for q in view.questions][:1]),
                         ('needs_clarification', (), [first.question]))

    def test_d156_an_attempted_pseudocyst_drainage_beside_a_bile_duct_drainage_asks_both(self):
        """The review's mix_attempted_pfc_beside_cbd, 43240 cited on P3 and separately on P4."""
        inv, text = two_drainages(ATTEMPTED_PFC, ATTEMPTED)
        reading = events.Reading.of(inv)
        link = mapping.code_link('43240')
        with self.subTest(part='fixture'):  # E2 meets the target and does not support; E3 supports and does not meet it
            self.assertEqual([(events.supports(reading, link, ('drainage',), reading.events[eid]),
                               events.defining_fit(reading, link, reading.events[eid])) for eid in ('E2', 'E3')],
                             [(False, True), (True, False)])
        for cited in ('P3', 'P4'):
            result = run(inv, text, [('43240', {'P3': ATTEMPTED_PFC, 'P4': DRAINAGE_LINES['bile_duct']}[cited])])
            with self.subTest(cited=cited, part='assess'):  # 4f82e5056: [target, target], E3 alone, no consideration
                self.assert_both(result, ATTEMPTED_Q, ATTEMPTED_REASON, 'bile_duct',
                                 ['performed_status', 'target', 'target'], True)  # D161 (1): the hold's, then R6's
                self.assertEqual(proposal(result, '43240').clarifications[2].question, R6_TARGET)
                self.assertEqual(proposal(result, '43240').support['reason'], events.ATTEMPTED)
            with self.subTest(cited=cited, part='completeness'):
                self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d156_the_gallbladder_twin_likewise(self):
        """The review's mix_attempted_pfc_beside_gb (tools/rv_refute2.py), with 43259 beside it as well."""
        inv, text = two_drainages(ATTEMPTED_PFC, ATTEMPTED, other='gallbladder')
        exam_line = 'The linear echoendoscope was advanced to the stomach.'
        for cited, picks in (('P3 the attempted pseudocyst drainage', [('43240', ATTEMPTED_PFC)]),
                             ('P4 the gallbladder drainage', [('43240', DRAINAGE_LINES['gallbladder'])]),
                             ('P3, beside 43259', [('43240', ATTEMPTED_PFC), ('43259', exam_line)])):
            with self.subTest(codes=len(picks), cited=cited):  # D161 (4): one label per citation
                self.assert_both(run(inv, text, picks), ATTEMPTED_Q, ATTEMPTED_REASON, 'gallbladder',
                                 ['performed_status', 'target', 'target'], True)

    def test_d156_a_pseudocyst_drainage_told_later_asks_its_time_beside_the_target(self):
        """The review's mix_later_pfc_beside_cbd: e5628be56 asked event_time about it, 4f82e5056 only the target
        hold's question (the drainage listed in doubt and asked at service scope); now both - and the listing stays as
        4f82e5056 gives it (the code reads what the hold reads). D161: 43240 asks the time with e5628be56's own words,
        so the service question, the same question, fact and words, is the code's (D89)."""
        inv, text = two_drainages(LATER_PFC, dict(time=a('current_encounter', 'Later', ['P3'])))
        result = run(inv, text, [('43240', LATER_PFC)])
        with self.subTest(part='assess'):
            self.assert_both(result, LATER_Q, 'CPT Studio could not confirm from the document when the drainage (stent) '
                             'of the A 9 cm pancreatic pseudocyst in the pancreas was done.', 'bile_duct',
                             ['event_time', 'target', 'target'], False)
        with self.subTest(part='listing'):  # 4f82e5056's item kept; D161: its service question is now 43240's own
            self.assertEqual([(item['service'], item['reason'], item['events'])
                              for item in result.completeness['unresolved_items']], [('gi.eus', 'in_doubt', ['E2'])])
            # D89: a code's question suppresses a service question only when it is the same question, fact and words -
            # 43240's first clarification is ('event_time', LATER_Q), as e5628be56 asked it
            self.assertEqual(proposal(result, '43240').clarifications[0].question, LATER_Q)
            self.assertEqual([(spec.scope, spec.fact, spec.question) for spec in result.clarifications], [])

    def test_d156_with_the_examinations_own_target_verified_both_are_still_asked(self):
        """Constructed (D156's recorded residual): with the examination's own target verified, R6 asks no structure
        examined; D156's one question carried 7.4's fact alone ([performed_status], where 4f82e5056 asks [target]).
        D161 (1): the hold's question is its own clarification - [performed_status, target]."""
        inv, text = two_drainages(ATTEMPTED_PFC, ATTEMPTED, other='gallbladder', examined=True)
        self.assert_both(run(inv, text, [('43240', ATTEMPTED_PFC)]), ATTEMPTED_Q, ATTEMPTED_REASON, 'gallbladder',
                         ['performed_status', 'target'], True)  # D161 (1): the residual closed - both facts

    def test_d156_controls_no_candidate_meets_the_target_or_none_supports(self):
        """Unchanged from 4f82e5056: with no candidate meeting the target the hold asks its own question alone
        (g1_gallbladder_43240: [target, target]); with no act supporting it, 7.4 decides as before (the uncertain
        pseudocyst drainage beside the gallbladder's, whose doubt reaches both); a pseudocyst drainage that supports it
        leaves 43240 READY on it alone."""
        inv, text = gallbladder()
        with self.subTest(control='gallbladder'):
            p = proposal(run(inv, text, [('43240', GB['P4'])]), '43240')
            reason, question = wording.defining_target_hold('43240', 'drainage', 'gallbladder', GB['P4'])
            self.assertEqual((asked(p), p.clarifications[0].question, p.support['question_events'],
                              p.support['reason']), (['target', 'target'], question, ['E2'], events.ANOTHER_SITE))
        inv, text = two_drainages(UNCLEAR_PFC, dict(status='uncertain', status_words='It is unclear whether'),
                                  other='gallbladder')
        with self.subTest(control='uncertain'):
            p = proposal(run(inv, text, [('43240', UNCLEAR_PFC)]), '43240')
            self.assertEqual((asked(p), p.support['reason'], p.support['question_events']),
                             (['performed_status', 'target'], events.DOUBT, ['E2']))
        inv, text = two_drainages(DRAINAGE_LINES['pseudocyst'], {}, other='gallbladder')
        with self.subTest(control='supported'):
            p = proposal(run(inv, text, [('43240', DRAINAGE_LINES['pseudocyst'])]), '43240')
            self.assertEqual((p.status, asked(p), [item['id'] for item in p.support['acts']]), ('ready', [], ['E2']))


# --- (3) an act already reportable is recorded once ---------------------------------------------------------------------

UNCLEAR_RFA = dict(RFA, P5='It is unclear whether the ablation was completed.')


class AReportableActIsNeverAlsoDoubted(SimpleTestCase):
    """D156 (3), problem 5 (low, wording): 4f82e5056 records a done stent beside 'No stent was placed across the
    pylorus.' as reportable AND doubted, and asks 'Is 43259 reported separately from stent placement, stent placement
    (stated in doubt) for this examination?'; e5628be56 asked '... from stent placement ...'. Held on every engine."""

    def test_d156_a_done_stent_beside_an_unresolved_denial_is_recorded_once(self):
        inv, text = with_examination(DENIED, stent(), denial())
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):  # reportable (D137), with an UNRESOLVED relation on it
            event = reading.events['E2']
            self.assertEqual((coverage.eus_guided_act(event), [item['type'] for item in reading.relations_of('E2')],
                              coverage.eus_unprofiled_doubt(reading, event)), (True, ['unresolved'], False))
        result = run(inv, text, [('43259', GE['P2'])])
        with self.subTest(part='assess'):
            base_held(self, result, '43259', (STENT_PLACEMENT,))
        with self.subTest(part='record'):
            self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')),
                             ([('E2', 'stent', STENT_PLACEMENT)], []))

    def test_d156_controls_an_act_that_is_not_reportable_stays_doubted(self):
        """The r5d arm-(d) input (the LAMS beside the denial: its kind not usable, so not reportable) is still doubted;
        an uncertain ablation beside a done one keeps its own doubted entry."""
        inv, text = related_case()
        with self.subTest(control='lams'):
            result = run(inv, text, [('43259', GE['P2'])])
            base_held(self, result, '43259', (IN_DOUBT,))
            self.assertEqual(entries(result, 'doubted'), [('E2', 'stent', STENT_PLACEMENT)])
        rfa = act('E2', 'P4', 'ablation', 'radiofrequency ablation', status_words='was performed',
                  procedure=a('eus', 'EUS-guided', ['P4']), target=tg('L1', 'pancreas', 'the pancreatic head mass',
                                                                     ['P4']))
        doubt = act('E3', 'P5', 'ablation', 'ablation', status='uncertain', status_words='It is unclear whether',
                    procedure=a('eus', 'EUS-guided', ['P4']))
        inv, text = with_examination(UNCLEAR_RFA, rfa, doubt)
        with self.subTest(control='uncertain_ablation'):
            result = run(inv, text, [('43259', GE['P2'])])
            self.assertEqual((entries(result, 'reportable'), entries(result, 'doubted')),
                             ([('E2', 'ablation', 'ablation')], [('E3', 'ablation', 'ablation')]))
            base_held(self, result, '43259', ('ablation', 'ablation (stated in doubt)'))
