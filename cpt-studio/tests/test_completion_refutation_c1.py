"""Refutation of the integrated completion diff, cycle 1 (2026-11-06; HARNESS.md "Refutation of the integrated diff,
cycle 1"): every counterexample the seven lenses measured, verified by the owner session on the head and on the base,
pinned here with the outcome the repair gives it, and the controls each repair must leave alone. Every document is
synthetic. A pin reads the engine as the website reads it (tests.test_harness_engine.run: real routing, the real
documented-service inventory, the participants' readings where a lens used them)."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio import review
from studio.gi import structure
from studio.validation import questions
from tests.test_completion_parity import heading_twin, named_twin
from tests.test_harness_engine import code, corti, read, run, span

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
REPORT_HEAD = BANNER + ('Gastroenterology Procedure Report\nDate of service: 2026-10-14\n'
                        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
EGD = ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus and to the second '
       'portion of the duodenum. Cold forceps biopsies were obtained from the distal esophagus.')
COL = ('Colonoscopy: The colonoscope was introduced through the anus and advanced to the cecum. A 6 mm polyp in the '
       'sigmoid colon was removed with a cold snare.')
BX = 'Cold forceps biopsies were obtained from the distal esophagus.'
SN = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
COLON_HEAD = BANNER + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
UPPER_HEAD = BANNER + 'EGD report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
ADVANCED = 'The colonoscope was advanced to the cecum and the examination was completed.\n'


def outcome(text, picks, readings=()):
    """{code: (bucket, status)} of the selected and excluded proposals (alternatives left out)."""
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]), list(readings))
    return {p.code: (p.bucket, p.status) for p in result.proposals if p.bucket != 'alternative'}


def ready(text, picks, readings=()):
    return {c for c, (bucket, status) in outcome(text, picks, readings).items() if (bucket, status) == ('selected', 'ready')}


class LabelledParagraphTests(SimpleTestCase):
    """structure lens. Cycle 1 held an announced, appended, another person's or summary-dated narrative with word readers
    (N3's deixis, present-occasion and attribution reads, N2's summary dating, P4's first-summary rule); cycle 2 refuted
    them both ways, and the approach changed to layout parity (HARNESS.md "Refutation of the integrated diff, cycle 2";
    tests/test_completion_parity.py): a labelled paragraph reads as its heading twin. Each input here reads exactly as its
    twin does - READY, the installed engine's own reading of the twin, recorded as its residual - and N1's negative
    quantifier still holds "None of this was done today." inside the paragraph."""

    def same_as_twin(self, text, picks, expected):
        self.assertEqual(ready(text, picks), ready(heading_twin(text), picks))
        self.assertEqual(ready(text, picks), expected)

    def test_an_announced_or_attributed_earlier_narrative_reads_as_its_heading_twin(self):
        for ind in ('Indications: Surveillance. Her colonoscopy in 2022 is reprinted here for reference.\n',
                    'Indications: Surveillance. Her colonoscopy in 2022 is carried forward for reference.\n',
                    'Indications: Surveillance. Her 2022 colonoscopy is shown for comparison.\n'):
            with self.subTest(ind):
                self.same_as_twin(REPORT_HEAD + ind + COL + '\nImpression: Sigmoid polyp removed.\n', [('45385', SN)],
                                  {'45385'})
        text = REPORT_HEAD + 'Indications: Dysphagia. The next paragraph is from her 2023 visit at another hospital.\n' + \
            EGD + '\nImpression: Esophageal biopsies.\n'
        self.same_as_twin(text, [('43239', BX)], {'43239'})

    def test_an_earlier_paragraph_pointing_at_the_next_reads_as_its_heading_twin(self):
        text = REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\n' + EGD + \
            ' The paragraph that follows belongs to her sister.\n' + COL + \
            '\nImpression: Esophageal biopsies; sigmoid polyp removed.\n'
        self.same_as_twin(text, [('43239', BX), ('45385', SN)], {'43239', '45385'})

    def test_an_appended_prior_report_reads_as_its_heading_twin(self):
        text = REPORT_HEAD + 'Indications: Dysphagia.\n' + EGD + '\nImpression: Esophageal biopsies.\nPlan: Await ' \
            'pathology.\n\nPrior Colonoscopy Report 2022\nIndications: Surveillance.\n' + COL + \
            '\nImpression: Sigmoid polyp removed.\n'
        self.same_as_twin(text, [('43239', BX), ('45385', SN)], {'43239', '45385'})

    def test_a_denial_holds_and_a_summary_dating_reads_as_its_heading_twin(self):
        text = REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL + \
            ' None of this was done today.\nImpression: Sigmoid polyp removed.\n'
        self.assertEqual(ready(text, [('45385', SN)]), set())  # N1's negative quantifier, kept (stricter than the twin)
        text = REPORT_HEAD + 'Indications: Surveillance after adenomas.\n' + COL + '\nImpression: Sigmoid polyp removed in 2022.\n'
        self.same_as_twin(text, [('45385', SN)], {'45385'})

    def test_the_controls_still_release(self):
        """A dated history, a history in the impression, a common report title, a generic scope naming its tract."""
        for ind, tail in (('Indications: Surveillance; history of adenomatous polyps on colonoscopy in 2022.\n',
                           '\nImpression: Sigmoid polyp removed.\n'),
                          ('Indications: Surveillance after adenomas.\n',
                           '\nImpression: Sigmoid polyp removed. Prior polypectomy in 2022.\n')):
            with self.subTest(ind + tail):
                self.assertEqual(ready(REPORT_HEAD + ind + COL + tail, [('45385', SN)]), {'45385'})
        titled = BANNER + 'Colonoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD ' \
            '(fictional)\nIndications: Surveillance colonoscopy for personal history of adenomatous polyps.\n' + COL + \
            '\nImpression: Sigmoid polyp removed.\nPlan: Await pathology.\n'
        self.assertEqual(ready(titled, [('45385', SN)]), {'45385'})
        generic = REPORT_HEAD + 'Indications: Dysphagia and surveillance after adenomas.\nUpper endoscopy: The ' \
            'endoscope was inserted through the mouth and advanced to the second part of the duodenum. ' + BX + '\n' + \
            COL.replace('The colonoscope', 'The scope') + '\nImpression: Esophageal biopsies; sigmoid polyp removed.\n'
        self.assertEqual([why for _, why in structure.decisions(generic)], ['', ''])
        self.assertEqual(ready(generic, [('43239', BX), ('45385', SN)]), {'43239', '45385'})


class OutcomeTests(SimpleTestCase):
    """outcome lens: the instrument's course, the reach and a pronoun's failure read today's plain statements only."""

    def head(self, title='Colonoscopy'):
        return BANNER + f'{title}\nDate of service: 2026-10-14\n'

    def test_a_course_reads_as_its_named_twin(self):
        """Cycle 1's I12 and I13 (word readers over the course's sentence and the document) were refuted both ways in
        cycle 2 and replaced by parity: the instrument's course names its family as "Procedure: Colonoscopy" names it, and
        is read no more permissively than that twin. "Status: Cancelled" holds both; the other two read READY in both
        forms (the installed engine's own reading of the named form, recorded as its residual)."""
        for body, quote, expected in (
                ('Indications: Surveillance.\nProcedure: The colonoscope was advanced to the cecum.\nStatus: Cancelled - '
                 'inadequate bowel preparation.\n', 'The colonoscope was advanced to the cecum', set()),
                ('Indications: Screening.\nProcedure: The colonoscope was advanced to the cecum on a prior occasion.\n',
                 'The colonoscope was advanced to the cecum on a prior occasion', {'45378'}),
                ('Indications: Screening.\nProcedure: The patient states that the colonoscope was advanced to the '
                 'cecum.\n', 'the colonoscope was advanced to the cecum', {'45378'})):
            with self.subTest(body):
                text = self.head() + body
                self.assertEqual(ready(text, [('45378', quote)]), ready(named_twin(text, 'Colonoscopy'), [('45378', quote)]))
                self.assertEqual(ready(text, [('45378', quote)]), expected)

    def test_a_reach_of_another_attempt_never_completes_the_examination(self):
        text = self.head('Colonoscopy Report') + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the transverse ' \
            'colon. Cecal intubation was achieved on the previous attempt but not today. Cold forceps biopsies were ' \
            'obtained from the transverse colon.\n'
        result = run(text, corti(('45380', span(text, 'Cold forceps biopsies were obtained from the transverse colon'))))
        (biopsy,) = [p for p in result.proposals if p.code == '45380']
        self.assertIn('service.incomplete', [c.id for c in biopsy.checks])

    def test_a_pronoun_aborting_after_a_done_act_is_the_examinations(self):
        text = self.head('ERCP Report') + 'Procedure: ERCP\nThe duodenoscope was advanced to the second portion of the ' \
            'duodenum. Deep biliary cannulation was achieved. Biliary brushings were obtained from the stricture; it was ' \
            'then aborted because of oxygen desaturation.\n'
        self.assertEqual(ready(text, [('43260', 'Biliary brushings were obtained from the stricture')]), set())

    def test_a_passage_the_scope_failed_keeps_the_incompleteness(self):
        text = self.head('Colonoscopy Report') + 'Procedure: Colonoscopy\nThe colonoscope was inserted. A fixed loop in ' \
            'the sigmoid colon could not be traversed despite abdominal pressure. Cold forceps biopsies were obtained ' \
            'from the rectum.\n'
        result = run(text, corti(('45380', span(text, 'Cold forceps biopsies were obtained from the rectum'))))
        (biopsy,) = [p for p in result.proposals if p.code == '45380']
        self.assertIn('service.incomplete', [c.id for c in biopsy.checks])


class ActTests(SimpleTestCase):
    """acts lens: an aborted listed act, a modifier's purpose, an impossible or another occasion's removal, a site."""

    def test_the_counterexamples_are_not_ready(self):
        cases = (
            (COLON_HEAD + 'Procedure: Colonoscopy with cold snare polypectomy\n' + ADVANCED + 'A 7 mm sessile polyp was '
             'found in the transverse colon.\nThe polypectomy was aborted.\n',
             [('45385', 'Colonoscopy with cold snare polypectomy')], '45385'),
            (COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + 'Findings: A 30 mm flat lesion was found in the ascending '
             'colon.\nImpression: 30 mm flat lesion in the ascending colon. EMR referral placed for future resection.\n',
             [('45390', 'EMR referral placed')], '45390'),
            (UPPER_HEAD + 'Procedure: Upper endoscopy\nThe gastroscope was advanced to the second portion of the '
             'duodenum.\nFindings: An impacted meat bolus was found in the distal esophagus.\nRemoval of the bolus was '
             'impossible, so it was pushed into the stomach.\n', [('43247', 'Removal of the bolus was impossible')],
             '43247'),
            (UPPER_HEAD + 'Indication: Intermittent solid-food dysphagia.\nProcedure: Upper endoscopy with dilation\nThe '
             'gastroscope was advanced to the second portion of the duodenum.\nFindings: A Schatzki ring was found at 38 '
             'cm from the incisors. This ring was the site of her steak impaction in 2023; the impaction was removed '
             'endoscopically at that time. The ring was dilated with a 54 Fr Savary dilator over a guidewire.\n',
             [('43247', 'the impaction was removed endoscopically at that time')], '43247'),
        )
        for text, picks, held in cases:
            with self.subTest(held):
                self.assertNotIn(held, ready(text, picks))

    def test_an_anaphors_site_is_its_own_clauses_then_its_antecedents(self):
        text = BANNER + 'Upper endoscopy and colonoscopy report (fictional)\nDate of service: 2026-10-14\nProcedures: ' \
            'Upper endoscopy and colonoscopy\nThe gastroscope was advanced to the second portion of the duodenum. A ' \
            'swallowed coin was found in the gastric body.\nThe coin was removed with a Roth net, and the colonoscope ' \
            'was then advanced to the cecum.\n'
        got = ready(text, [('43247', 'The coin was removed with a Roth net'),
                           ('45379', 'The coin was removed with a Roth net')])
        self.assertEqual(got, {'43247'})

    def test_the_false_holds_are_released(self):
        # refutation cycle 3 (closed C3-5): a hedge that only heads a reason phrase naming no act is the reason's
        # diagnosis, so the listing is promoted - READY, as the installed release reads it (cycle 2 had held it, saying
        # the base did; the base reads it READY); the act's own "attempted" stays held
        reason = UPPER_HEAD + 'Procedure: Upper endoscopy with duodenal biopsies for suspected celiac disease\nThe ' \
            'gastroscope was advanced to the second portion of the duodenum.\nThe duodenal mucosa appeared normal.\n'
        self.assertEqual(ready(reason, [('43239', 'Upper endoscopy with duodenal biopsies for suspected celiac '
                                                  'disease')]), {'43239'})
        residual = COLON_HEAD + 'Procedure: Colonoscopy with hot snare polypectomy\n' + ADVANCED + 'A 25 mm sessile ' \
            'polyp was found in the cecum and was removed piecemeal. The residual polyp was left in place.\n'
        self.assertEqual(ready(residual, [('45385', 'Colonoscopy with hot snare polypectomy')]), {'45385'})

    def test_an_aborted_biopsy_is_held_and_a_second_ones_failure_is_not_the_firsts(self):
        quote = 'A 5 mm polyp in the ascending colon was biopsied with cold forceps.'
        for tail in ('The biopsy was aborted due to bleeding and no tissue was obtained.',
                     'Cold forceps biopsy was aborted due to bleeding.'):
            with self.subTest(tail):
                text = COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + quote + '\n' + tail + '\n'
                self.assertEqual(ready(text, [('45380', quote)]), set())
                self.assertEqual(ready(text, [], [read('astra', [code(text, '45380', quote)])]), set())
        other = COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + quote + '\nA second biopsy of the cecum was aborted ' \
            'due to bleeding.\n'
        self.assertEqual(ready(other, [('45380', quote)]), {'45380'})


class AdmissionTests(SimpleTestCase):
    """admission lens: another act's doubt, a code on its title alone, a failed technique, a removal before a failure."""

    P1 = ('Hot snare polypectomy of a 15 mm pedunculated polyp in the sigmoid colon was attempted, but the snare could '
          'not be closed around the stalk, and the polyp was left in place.')
    P2 = ('A 6 mm polyp in the transverse colon was removed with a cold snare, but it is unclear whether the polyp was '
          'removed or only biopsied.')

    def test_another_lesions_failure_never_releases_a_doubted_act_in_any_order(self):
        text = COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + self.P1 + '\n' + self.P2 + '\n'
        for picks, readings in (([('45385', self.P2)], [read('astra', [code(text, '45385', self.P1)])]),
                                ([('45385', self.P1)], []), ([('45385', self.P1)], [read('astra', [code(text, '45385',
                                                                                                         self.P2)])])):
            with self.subTest(picks):
                self.assertEqual(ready(text, picks, readings), set())
        # refutation cycle 2 (the two-cycle rule): the another-act release is abandoned, so a cited failed attempt held
        # the code even beside another polyp plainly removed (the declared cost, E|ANOTHER-failed-attempt). The walk round
        # (2026-11-07, finding 5) changes the approach: the closed-form failure cited beside the removed polyp's own
        # passage, by any proposer, is set aside (engine._set_aside_attempts) - READY; cited alone it holds (above). The
        # removed polyp's own passage, cited alone, is READY
        clean = COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + self.P1 + '\nA 6 mm polyp in the transverse colon ' \
            'was removed with a cold snare.\n'
        removed = 'A 6 mm polyp in the transverse colon was removed with a cold snare.'
        self.assertEqual(ready(clean, [('45385', self.P1)], [read('astra', [code(clean, '45385', removed)])]), {'45385'})
        self.assertEqual(ready(clean, [('45385', removed)]), {'45385'})

    def test_a_polyp_found_and_left_in_place_contradicts_the_listing(self):
        quote = 'A 10 mm polyp was found in the sigmoid colon and was left in place for surgical resection.'
        text = COLON_HEAD + 'Procedure: Colonoscopy with hot snare polypectomy\n' + ADVANCED + quote + '\n'
        self.assertNotIn('45385', ready(text, [('45378', ADVANCED.strip())], [read('astra', [code(text, '45385', quote)])]))
        self.assertNotIn('45385', ready(text, [('45385', quote)]))

    def test_a_dilation_technique_is_read_from_its_inflation_and_its_named_device(self):
        inflated = 'The stricture was dilated with a 15 mm dilator advanced over a guide wire and inflated to 6 atm for 60 seconds.'
        text = UPPER_HEAD + 'Procedure: Upper endoscopy with dilation\nThe endoscope was advanced to the second portion ' \
            'of the duodenum.\nA benign-appearing distal esophageal stricture was found.\n' + inflated + '\n'
        self.assertEqual(ready(text, [('43249', inflated)], [read('astra', [code(text, '43248', inflated)])]), {'43249'})
        # refutation cycle 2 (D2, D6): cycle 1's deferral of a generic wire-guided dilator to a balloon named beside it is
        # abandoned - two techniques named, each code fits, and proposed together they compete (owner question Q2);
        # Corti's 43248 alone reads READY, as the installed release reads it (it reads no technique)
        cre = 'The stricture was dilated to 15 mm with a CRE wire-guided balloon dilator.'
        text = UPPER_HEAD + 'Procedure: Upper endoscopy with dilation\nThe endoscope was advanced to the second portion ' \
            'of the duodenum.\nA benign-appearing distal esophageal stricture was found.\n' + cre + '\n'
        self.assertEqual(ready(text, [('43248', cre)]), {'43248'})
        self.assertEqual(ready(text, [('43248', cre)], [read('astra', [code(text, '43249', cre)])]), set())

    def test_a_removal_before_a_failed_technique_keeps_the_hold(self):
        text = COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + 'A 25 mm sessile polyp in the ascending colon was ' \
            'removed piecemeal and retrieved.\nEn bloc hot snare polypectomy failed.\n'
        got = outcome(text, [('45385', 'En bloc hot snare polypectomy failed.'), ('45378', ADVANCED.strip())])
        self.assertNotEqual(got['45385'], ('excluded', 'excluded'))
        self.assertNotEqual(got['45378'], ('selected', 'ready'))


class EarlierFormBindingTests(SimpleTestCase):
    """The rule for answers stored before the binding. Cycle 1 bound them by their own question's words; cycle 2 (answers
    W2, W4) refuted that - the words were engine prose the member never saw, which this release rewords - and they now
    bind by their (code, family, fact) key, as the installed release bound them."""

    def test_bind_reads_an_earlier_form_answer_by_its_key(self):
        key = ('45385', 'gi.colonoscopy', 'extent')
        asked = {key: 'f' * 64}

        def answer(**kw):
            return {'code': '45385', 'family': 'gi.colonoscopy', 'fact': 'extent', 'value': 'not_documented',
                    'question': '', 'answer_id': 'a1', **kw}
        bound, earlier = questions.bind([answer()], asked)
        self.assertEqual((len(bound), earlier), (1, []))
        bound, earlier = questions.bind([answer(code='45380')], asked)
        self.assertEqual((bound, [why for _, why in earlier]), ([], [questions.NO_LONGER_ASKED]))
        # a fingerprinted answer is read by its fingerprint alone, as before
        bound, earlier = questions.bind([answer(question='f' * 64)], asked)
        self.assertEqual(len(bound), 1)
        bound, earlier = questions.bind([answer(question='e' * 64)], asked)
        self.assertEqual((bound, [why for _, why in earlier]), ([], [questions.ASKED_DIFFERENTLY]))

    def test_the_word_binding_is_gone(self):
        for name in ('wording', 'group_wording', 'EARLIER', 'EARLIER_FORM'):
            self.assertFalse(hasattr(questions, name), name)


class WithdrawnEngineAnswerTests(SimpleTestCase):
    """answers lens F2 (cycle 1) reopened a withdrawn engine-applied answer's question in the overlay alone
    (review._reopened); cycle 2 (W1, W5, W6) refuted it - the other readers read the stored assessment and disagreed -
    and the stage-1 design returned: every surface reads the stored assessment until the withdrawal's recompute runs, and
    readiness holds meanwhile (review.STALE_ANSWER_BLOCKER; tests/test_completion_refutation_c2_answers.py)."""

    def test_the_overlay_reopen_is_gone_and_readiness_holds_instead(self):
        self.assertFalse(hasattr(review, '_reopened'))
        self.assertTrue(review.STALE_ANSWER_BLOCKER)

