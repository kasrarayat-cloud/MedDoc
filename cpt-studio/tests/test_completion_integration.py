"""Completion repair (owner directive 2026-11-06): the integration's own rules, measured on the merged builders.

- A dilation's technique (catalogue.CodeProfile.technique, reconcile.technique_fits): a one-technique dilation code
  never accounts for a dilation of another technique. The Word walk's h2c document (a Savary-Gilliard dilation over a
  guide wire) read 43249 (balloon) READY once builder R2's routing repair routed its upper endoscopy, and 43248 and 43249
  could both read READY for one dilation; the base read the same wherever such an EGD was routed.
- Competition reads every proposer alike (engine._competition): two codes the proposal provider alone selected for one
  act compete as a participant's would.
- One subject reading (services.predicate_subject): builder R2's structural walk unless builder A's attachment walk reads
  a different subject; the removal reader also needs the attachment walk to read it (services._removal_subject).
- A code the document supports by its own documented act is not held because its cited passage states another, failed
  act of its kind (the removed arm of engine._passages_elsewhere).
All texts are synthetic.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import catalogue, clauses
from studio.gi import services as gi_services
from studio.validation import reconcile
from tests.test_harness_engine import code, corti, proposal, read, run, span

SYN = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
EGD = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
       'Procedure\nThe gastroscope was passed to the second portion of the duodenum.\n')
COLON = (SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
         'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum.\n')
NONE_NAMED = 'Dilation was performed across the Schatzki ring to 18 mm under direct visualization.'
TTS = 'A through-the-scope balloon was positioned across the Schatzki ring and inflated to 18 mm.'
CRE = 'Over a guidewire, a CRE balloon dilator was passed and the stricture was dilated to 15 mm.'
SAVARY = 'Savary dilators of 14 and 15 mm were passed over a guide wire across the stricture.'
MALONEY = 'A 54 Fr Maloney bougie was passed across the ring.'
BOTH = 'Savary dilators of 14 and 15 mm were passed over a guide wire. Then an 18 mm TTS balloon was inflated across the ring.'
QUIET = ('pass', 'not_applicable', 'not_verified', 'info')


def statuses(text, picks, participants=None):
    """code -> status, Corti selecting ``picks`` ((code, quote) pairs); with ``participants`` a harness is configured
    (an empty Astra reading by default: the live workflow always has one)."""
    parts = [read('astra', [])] if participants is None else participants
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]), parts)
    return {p.code: p.status for p in result.proposals if p.bucket == 'selected'}


class DilationTechniqueTests(SimpleTestCase):
    def test_the_catalogue_names_each_one_technique_code(self):
        balloon = {c for c, p in catalogue.CODES.items() if p.technique == catalogue.BALLOON}
        wire = {c for c, p in catalogue.CODES.items() if p.technique == catalogue.WIRE_BOUGIE}
        self.assertEqual(balloon, {'43249', '43233', '43214', '43220', '44381', '45386', '44405', '45340', '43277'})
        self.assertEqual(wire, {'43248', '43226'})
        self.assertEqual(catalogue.CODES['43245'].technique, '')  # gastric or duodenal, any technique
        self.assertEqual(catalogue.CODES['43213'].technique, '')  # retrograde, balloon or dilator

    def test_the_techniques_a_passage_names(self):
        for text, named in ((TTS, {'balloon'}), (CRE, {'balloon'}), (SAVARY, {'wire_bougie'}), (MALONEY, {'bougie'}),
                            (NONE_NAMED, set()), ('The stricture was dilated over a guidewire to 15 mm.', set()),
                            ('A wire-guided polyvinyl dilator was passed.', {'wire_bougie'}),
                            ('Bougie dilation over the wire was performed.', {'wire_bougie'})):
            with self.subTest(text):
                self.assertEqual(set(reconcile.dilation_techniques(text)), named)

    def test_a_one_technique_code_reads_only_its_own_technique(self):
        for line, expected in ((TTS, {'43249': 'ready', '43248': 'needs_clarification'}),
                               (CRE, {'43249': 'ready', '43248': 'needs_clarification'}),
                               (SAVARY, {'43249': 'needs_clarification', '43248': 'ready'}),
                               (MALONEY, {'43249': 'needs_clarification', '43248': 'needs_clarification'})):
            text = EGD + line + '\n'
            for code_, status in expected.items():
                with self.subTest(line=line, code=code_):
                    self.assertEqual(statuses(text, [(code_, line)]), {code_: status})

    def test_the_held_code_says_which_dilation_the_document_states(self):
        text = EGD + SAVARY + '\n'
        item = proposal(run(text, corti(('43249', span(text, SAVARY))), [read('astra', [])]), '43249')
        self.assertEqual(item.status, 'needs_clarification')
        question = item.clarifications[0].question
        self.assertIn('dilation with dilators passed over a guide wire', question)
        self.assertIn('Was a balloon dilation performed on the date of service?', question)
        self.assertNotIn('not documented', question.lower())

    def test_an_impression_with_no_technique_restates_the_narratives(self):
        text = EGD + SAVARY + '\nImpression: Esophageal stricture, dilated to 15 mm.\n'
        self.assertEqual(statuses(text, [('43249', SAVARY[:30])]), {'43249': 'needs_clarification'})
        self.assertEqual(statuses(text, [('43248', SAVARY[:30])]), {'43248': 'ready'})

    def test_the_h2c_walk_document(self):
        from tests.test_participants_support import FIXTURES
        from studio.gi import context as gi_context, detect
        from studio.types import NormalizedResponse
        from studio.validation.engine import assess
        from tests.test_harness_engine import REFERENCE
        text = (FIXTURES / 'fable-walk' / 'h2c.context.txt').read_text(encoding='utf-8')
        day = date(2026, 10, 28)  # the document's own date of service
        quote = 'Savary-Gilliard'
        for picks, expected in (([('43249', quote)], {'43249': 'needs_clarification'}),
                                ([('43248', quote)], {'43248': 'ready'}),
                                ([('43248', quote), ('43249', quote)], {'43248': 'ready', '43249': 'needs_clarification'})):
            with self.subTest([c for c, _ in picks]):
                codes = corti(*[(c, span(text, q)) for c, q in picks])
                result = assess(text=text, pages=(), context=gi_context.extract_context(text),
                                routing=detect.route(text, day), normalized=NormalizedResponse('corti', 'test@1', tuple(codes)),
                                reference=REFERENCE, service_date=day, provider_status='succeeded',
                                participants=(read('astra', []),))
                self.assertEqual({p.code: p.status for p in result.proposals if p.bucket == 'selected'}, expected)

    def test_unstated_or_two_techniques_are_left_to_the_reviewer(self):
        # no technique named: both codes account for the one dilation, so they compete (held). Two techniques named for
        # dilations whose sites the reader leaves unread: each code has a dilation of its own technique, and the two are
        # still held as competing (engine._same_claim errs toward one act) - the owner's coding question Q2 (two
        # dilation techniques on one stricture, NCCI) stays the owner's, and nothing is READY on CPT Studio's choice
        self.assertEqual(statuses(EGD + NONE_NAMED + '\n', [('43248', NONE_NAMED), ('43249', NONE_NAMED)]),
                         {'43248': 'needs_clarification', '43249': 'needs_clarification'})
        self.assertEqual(statuses(EGD + BOTH + '\n', [('43248', BOTH[:30]), ('43249', BOTH[:30])]),
                         {'43248': 'needs_clarification', '43249': 'needs_clarification'})


class OneEvaluationCompetitionTests(SimpleTestCase):
    def test_corti_alone_proposing_two_codes_for_one_act_is_held_as_a_participant_would_be(self):
        text = EGD + NONE_NAMED + '\n'
        by_corti = statuses(text, [('43248', NONE_NAMED), ('43249', NONE_NAMED)])
        participant = run(text, corti(('43249', span(text, NONE_NAMED))),
                          [read('astra', [code(text, '43248', NONE_NAMED)])])
        by_both = {p.code: p.status for p in participant.proposals if p.bucket == 'selected'}
        self.assertEqual(by_corti, {'43248': 'needs_clarification', '43249': 'needs_clarification'})
        self.assertEqual(by_corti, by_both)

    def test_a_guide_wire_code_beside_a_balloon_dilation_is_no_rival(self):
        text = EGD + TTS + '\n'
        result = run(text, corti(('43248', span(text, TTS))), [read('astra', [code(text, '43249', TTS)])])
        found = {p.code: p for p in result.proposals if p.bucket == 'selected'}
        self.assertEqual((found['43249'].status, found['43248'].status), ('ready', 'needs_clarification'))
        self.assertFalse(any(c.id == 'proposals.competing' for c in found['43249'].checks))


class CitedFailedAttemptTests(SimpleTestCase):
    def test_a_code_the_document_supports_is_not_held_for_citing_another_failed_act(self):
        failure = 'Hot snare polypectomy was attempted, but the polypectomy was unsuccessful.'
        done = 'A 6 mm polyp in the ascending colon was removed with a cold snare and retrieved.'
        text = COLON + done + '\n' + failure + '\n'
        item = proposal(run(text, corti(('45385', span(text, failure))), [read('astra', [])]), '45385')
        self.assertEqual(item.status, 'ready')
        self.assertEqual(item.support['unrelated'], [0])  # the cited passage is recorded as about another act
        # alone, the failed attempt is still never READY
        alone = COLON + failure + '\n'
        self.assertNotEqual(proposal(run(alone, corti(('45385', span(alone, failure))), [read('astra', [])]),
                                     '45385').status, 'ready')


class OneSubjectReadingTests(SimpleTestCase):
    @staticmethod
    def at(sentence, word='was'):
        return list(re.finditer(r'\b' + word + r'\b', sentence))[-1].start()

    def test_the_walks_agree_and_the_reading_is_theirs(self):
        for sentence, head in (('A 6 mm polyp was removed with a cold snare.', 'polyp'),
                               ('Fragments of the bolus were removed.', 'fragments'),
                               ('Hot snare polypectomy of a 12 mm pedunculated polyp was attempted.', 'polypectomy')):
            with self.subTest(sentence):
                verb = 'were' if ' were ' in sentence else 'was'
                found = gi_services.predicate_subject(sentence, 0, self.at(sentence, verb))
                self.assertEqual(found.head.word, head)
                self.assertIsNotNone(gi_services._removal_subject(sentence, 0, self.at(sentence, verb)))

    def test_where_the_walks_disagree_neither_is_believed(self):
        for sentence in ('The overtube protecting the meat bolus was removed.',
                         'The steak impaction passed after the overtube was removed.',
                         'The food bolus impacted before presentation was removed with a Roth net.'):
            with self.subTest(sentence):
                pos = self.at(sentence)
                self.assertIsNotNone(clauses.subject(sentence, 0, pos))
                self.assertIsNotNone(gi_services._attachment_subject(sentence, 0, pos))
                self.assertIsNone(gi_services.predicate_subject(sentence, 0, pos))
                self.assertIsNone(gi_services._removal_subject(sentence, 0, pos))

    def test_where_the_attachment_walk_reads_nothing_the_structural_walk_stands(self):
        sentence = 'A polyp in the ascending colon was removed with a cold snare.'
        pos = self.at(sentence)
        self.assertIsNone(gi_services._attachment_subject(sentence, 0, pos))
        self.assertEqual(gi_services.predicate_subject(sentence, 0, pos).head.word, 'polyp')
        self.assertIsNone(gi_services._removal_subject(sentence, 0, pos))  # the removal reader needs both

    def test_a_pronoun_is_read_through_the_clause_before_it(self):
        # refutation cycle 3 (outcome C3-1, C3-2): the pronoun rule is abandoned - a pronoun subject stays unresolved,
        # the examination's failure, the base reading
        text = 'Polypectomy was attempted. It was unsuccessful.'
        clause = text.index('It')
        found = gi_services.predicate_subject(text, clause, self.at(text), (0, clause))
        self.assertTrue(found.pronoun)
        self.assertNotEqual(clauses.failure_of(text, found), clauses.SUB_ACT)


class ReferencePathTests(SimpleTestCase):
    def test_the_fixture_used_above_exists(self):
        from tests.test_participants_support import FIXTURES
        self.assertTrue(Path(FIXTURES / 'fable-walk' / 'h2c.context.txt').exists())


class DatedHistoryInTheIndicationTests(SimpleTestCase):
    """structure's N3 (integration): an indication whose every mention of the family is an earlier occasion dated
    before the service date by its own clause names history, so the labelled paragraph after it reads as it reads under
    a "Procedure:" heading. Undated, planned, announced or introduced occasions still hold it."""
    HEAD = (SYN + 'Gastroenterology Procedure Report\nDate of service: 2026-10-14\n'
            'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
    SNARE = 'A 5 mm polyp in the transverse colon was removed with a cold snare.'

    def snare(self, indication, label=True):
        body = ('Colonoscopy: ' if label else 'Procedure: Colonoscopy\n') + 'The colonoscope was advanced to the cecum. '
        text = self.HEAD + indication + '\n' + body + self.SNARE + '\n'
        return statuses(text, [('45385', self.SNARE)])['45385']

    def test_a_dated_earlier_occasion_reads_as_the_heading_form_does(self):
        for indication in ('Indications: Surveillance; history of adenomatous polyps on colonoscopy in 2022.',
                           'Indications: Personal history of colon polyps (last colonoscopy 2022).',
                           'Indications: Prior colonoscopy in 2019 showed two adenomas; surveillance today.',
                           'Indications: Surveillance after a colonoscopy at an outside hospital in 2023.',
                           'Indications: Colonoscopy on 10/01/2026 showed a mass.'):
            with self.subTest(indication):
                self.assertEqual(self.snare(indication), 'ready')
                self.assertEqual(self.snare(indication, label=False), 'ready')

    def test_an_undated_planned_announced_or_introduced_occasion_still_holds(self):
        for indication in ('Indications: Hx colonoscopy.', 'Indications: Follow-up after colonoscopy.',
                           'Indications: Review of colonoscopy.', 'Indications: Colonoscopy planned for 12/01/2026.',
                           'Indications: Colonoscopy images reviewed.',  # historical, but undated
                           'Indications: Surveillance. She had a colonoscopy in 2020, described next.',
                           'Indications: Surveillance; the findings of the colonoscopy in 2019 follow.',
                           'Indications: Colonoscopy in 2019 at an outside hospital:',
                           'Indications: Surveillance; the colonoscopy report from 2019 is attached.',
                           'Indications: Colonoscopy in 2022; colonoscopy for surveillance after an outside'):
            with self.subTest(indication):
                self.assertNotEqual(self.snare(indication), 'ready')

    def test_the_paragraphs_own_other_time_still_holds_after_a_dated_history(self):
        text = (self.HEAD + 'Indications: Surveillance; history of polyps on colonoscopy in 2022.\n'
                'Colonoscopy: The colonoscope was advanced to the cecum in 2022. ' + self.SNARE + '\n')
        self.assertNotEqual(statuses(text, [('45385', self.SNARE)])['45385'], 'ready')

    def test_follow_announces_and_follow_up_does_not(self):
        self.assertNotEqual(self.snare('Indications: Surveillance; details of the colonoscopy in 2019 follow.'), 'ready')
        self.assertEqual(self.snare('Indications: Follow-up colonoscopy after polypectomy in 2023.'), 'ready')


class AnotherActsDoubtTests(SimpleTestCase):
    """engine._another_acts_doubt (integration): a proposer's passage about another, not-done act of the code's kinds
    never holds a code whose own documented act no passage doubts; a passage that also states the matched act keeps the
    routing-era reader's hold (the NEG-REL refuters of the completion corpus)."""
    HEAD = (SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
            'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the ileocecal valve was identified.\n')
    COLD = 'A 6 mm polyp in the transverse colon was removed with a cold snare.'
    FAILED = ('Hot snare polypectomy of a 15 mm pedunculated polyp in the sigmoid colon was attempted, but the snare could '
              'not be closed around the stalk, and the polyp was left in place.')

    def test_a_participants_passage_about_the_failed_attempt_holds_the_code_for_the_reviewer(self):
        # refutation cycle 2 (the two-cycle rule): the integration's another-act release is abandoned - refuted in
        # cycles 1 and 2 - so a passage about another polyp's failed attempt, cited by any proposer, holds the code for
        # the reviewer (the installed release's reading); the done polyp's own passage cited alone is READY
        text = self.HEAD + self.COLD + '\n' + self.FAILED + '\n'
        result = run(text, corti(('45385', span(text, self.COLD))), [read('astra', [code(text, '45385', self.FAILED)])])
        item = proposal(result, '45385')
        self.assertEqual(item.status, 'needs_clarification')
        self.assertEqual((item.support['supporting'], item.support['unrelated']), ([0], [1]))
        alone = proposal(run(text, corti(('45385', span(text, self.FAILED))), [read('astra', [])]), '45385')
        self.assertEqual(alone.status, 'needs_clarification')
        own = proposal(run(text, corti(('45385', span(text, self.COLD))), [read('astra', [])]), '45385')
        self.assertEqual(own.status, 'ready')

    def test_the_failed_attempt_alone_is_never_ready(self):
        text = self.HEAD + self.FAILED + '\n'
        item = proposal(run(text, corti(('45385', span(text, self.FAILED))), [read('astra', [])]), '45385')
        self.assertNotEqual(item.status, 'ready')

    def test_a_passage_that_also_states_the_matched_act_keeps_the_hold(self):
        line = 'In the distal rectum, a 5 mm sessile polyp was seen; zero (0) biopsies were taken; it was not snared.'
        text = self.HEAD + line + '\n'
        item = proposal(run(text, corti(('45380', span(text, line))), [read('astra', [])]), '45380')
        self.assertNotEqual(item.status, 'ready')
