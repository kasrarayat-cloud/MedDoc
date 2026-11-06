"""Refutation of the integrated completion diff, cycle 2, outcome lens (2026-11-06; HARNESS.md "Completion repair
(2026-11-06)"): builder O's three mechanisms, each replacing a cycle-1 patch the cycle refuted, pinned with the findings
they repair (refute/results-c2.json, lens "outcome": O2, O5, O6, O8 and the reach half of O7), the variants the lens
measured, the controls each must leave alone, and a twin in another layout or GI family.

- The reach statement (detect._completion_states_reach) is a closed positive form: a sentence states the landmark
  reached only when a small grammar recognises it whole - the landmark itself (after at most "the"), "was/were", at
  most one adverb of a closed class, a completion participle of a closed class, at most one tail of a closed class, and
  the sentence's end. Anything else keeps the extent's base reading. Each sentence is read once.
- A pronoun's failure (services.predicate_subject): a pronoun is read through the clause before it only where that
  clause's OWN main predicate is an attempt or a failure of a closed class; a singular pronoun never stands for a plural
  subject. Otherwise it stays unresolved: the examination's failure, the base reading.
- One failure vocabulary (cues.ACT_*): routing's subject-tested failure cues and the services reader's FAILED_ACT,
  FAILED_ACT_BEFORE and ATTEMPT_OR_FAILURE_CUES are built from the same words.

Every document is synthetic. A pin reads the engine as the website reads it (tests.test_harness_engine.run: real
routing and the real documented-service inventory)."""
from __future__ import annotations

import re
import time
from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from studio.gi import cues, detect, sections
from studio.gi import services as gi_services
from tests.test_harness_engine import DAY, corti, run, span

QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON_HEAD = BANNER + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
UPPER_HEAD = BANNER + 'EGD report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
ERCP_HEAD = BANNER + 'ERCP report (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient department\n'
REPORT_HEAD = BANNER + 'Gastroenterology Procedure Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic ' \
    'Endoscopist, MD (fictional)\n'
ADVANCED = 'The colonoscope was advanced to the cecum and the examination was completed.\n'
EGD_IN = 'The gastroscope was advanced to the second portion of the duodenum.\n'
BX = 'Cold forceps biopsies were obtained from the transverse colon.'


def head(title):
    return BANNER + f'{title}\nDate of service: 2026-10-14\n'


def proposals(text, picks):
    """{code: proposal} of the selected and excluded proposals (alternatives left out)."""
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]))
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}


def label(p):
    return {('selected', 'ready'): 'READY', ('selected', 'needs_clarification'): 'HELD'}.get((p.bucket, p.status),
                                                                                            f'{p.bucket}/{p.status}')


def flagged(p):
    return {c.id for c in p.checks if c.status not in QUIET}


def incompleteness_considered(p):
    return any('ncomplete' in m for m in p.modifier_considerations)


def finding(text, family, day=DAY):
    return detect.route(text, day).finding(family)


def extent(text, family='gi.colonoscopy', day=DAY):
    found = finding(text, family, day)
    return next((f.value for f in found.facts if f.name == 'extent'), None) if found else None


class _Counting:
    """A compiled pattern's stand-in that counts its fullmatch calls (the reach statement's reads)."""

    def __init__(self, pattern):
        self.pattern, self.calls = pattern, 0

    def fullmatch(self, *args):
        self.calls += 1
        return self.pattern.fullmatch(*args)


# --- the reach statement ---------------------------------------------------------------------------------------------
REACH_HEAD = head('Colonoscopy Report') + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the transverse colon. '
PLAIN_HEAD = head('Colonoscopy Report') + 'Procedure: Colonoscopy\nThe colonoscope was inserted. '
ANOTHER_OCCASION = (
    'Her last colonoscopy was three years ago. Cecal intubation was achieved in that examination.',  # O5
    'Cecal intubation was achieved during the procedure that preceded her hemicolectomy.',  # O5 variant
    'Cecal intubation was achieved during the procedure her sister had.',  # O5 variant
    'Cecal intubation was achieved on the previous attempt but not today.',  # the cycle-1 pin
    'Perhaps cecal intubation was achieved.',  # a hedge outside services.HEDGE_WORDS
    'Whether cecal intubation was achieved is not documented.',
    'Cecal intubation was achieved?',
)
CLOSED_FORMS = (
    'Cecal intubation was achieved.',
    'Cecal intubation was achieved, as confirmed by photographs of the appendiceal orifice.',  # O7, the reach half
    'Cecal intubation was achieved, as confirmed by visualization of the appendiceal orifice and the ileocecal valve.',
    'Cecal intubation was confirmed by photodocumentation of the appendiceal orifice.',
    'Cecal intubation was achieved without difficulty.',
    'Cecal intubation was achieved and photodocumented.',
    'Cecal intubation was successfully achieved.',
)


class ReachStatementTests(SimpleTestCase):
    """Cycle 2, outcome O5, O7 (the reach half) and O8: the reach statement as a closed positive form."""

    def test_d10b_a_plain_reach_statement_reads_the_extent(self):
        """Cycle 2, outcome: the requirement the reach reader exists for (corpus D|ARCH-D10b, which alone moves to a false
        hold without it): "Cecal intubation was achieved." reads the cecum reached, and the polypectomy is READY with no
        incompleteness."""
        corpus_text = ('Date of service: 11/05/2026\nProcedure: Colonoscopy.\nCecal intubation was achieved. A 6 mm sigmoid '
                       'polyp was removed with a cold snare.\n')
        self.assertEqual(extent(corpus_text, day=date(2026, 11, 5)), 'cecum')
        text = BANNER + 'Colonoscopy Report\nDate of service: 2026-10-14\nProcedure: Colonoscopy.\nCecal intubation was ' \
            'achieved. A 6 mm sigmoid polyp was removed with a cold snare.\n'
        polypectomy = proposals(text, [('45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')])['45385']
        self.assertEqual(label(polypectomy), 'READY')
        self.assertNotIn('service.incomplete', flagged(polypectomy))
        self.assertEqual(extent(text), 'cecum')

    def test_another_occasions_or_a_doubted_reach_keeps_the_base_reading(self):
        """Cycle 2, outcome O5 and its two variants (another examination's, another procedure's, another person's
        reach), the cycle-1 pin, a hedge, an open question and a question: the scope reached the transverse colon today,
        so the colonoscopy reads incomplete as the installed release reads it, 45380 stays READY with its incompleteness
        warning, and the "Incomplete procedure" modifier consideration is kept."""
        for sentence in ANOTHER_OCCASION:
            with self.subTest(sentence):
                text = REACH_HEAD + sentence + ' ' + BX + '\n'
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')
                self.assertEqual(extent(text), 'incomplete: transverse colon')
                biopsy = proposals(text, [('45380', BX)])['45380']
                self.assertEqual(label(biopsy), 'READY')
                self.assertIn('service.incomplete', flagged(biopsy))
                self.assertTrue(incompleteness_considered(biopsy), biopsy.modifier_considerations)

    def test_a_closed_tail_or_adverb_still_reads_the_reach(self):
        """Cycle 2, outcome O7 (the reach half): "Cecal intubation was achieved, as confirmed by photographs of the
        appendiceal orifice." had been held with an extent question by the cycle-1 doubt reader ("by photographs" read as
        an agent); every form of the closed grammar reads the cecum reached and 45380 READY."""
        for sentence in CLOSED_FORMS:
            with self.subTest(sentence):
                text = PLAIN_HEAD + sentence + ' ' + BX + '\n'
                self.assertEqual(extent(text), 'cecum')
                self.assertEqual(label(proposals(text, [('45380', BX)])['45380']), 'READY')

    def test_an_unrecognised_sentence_keeps_the_base_hold(self):
        """Cycle 2, outcome O7 (the reach half), the safe side: a sentence the grammar does not recognise whole is no
        reach statement, and the installed release's reading stands - held for the extent ("... and the previous
        polypectomy site was inspected.", "... after abdominal pressure was applied.") or no extent read at all."""
        for sentence in ('Cecal intubation was achieved and the previous polypectomy site was inspected.',
                         'Cecal intubation was achieved after abdominal pressure was applied.'):
            with self.subTest(sentence):
                text = PLAIN_HEAD + sentence + ' ' + BX + '\n'
                self.assertIsNone(extent(text))
                biopsy = proposals(text, [('45380', BX)])['45380']
                self.assertEqual(label(biopsy), 'HELD')
                self.assertIn('extent', [c.fact for c in biopsy.clarifications])
        for sentence in ('Cecal intubation was not achieved.', 'Cecal intubation was achieved, but the terminal ileum was '
                         'not intubated.', 'If cecal intubation was achieved, the cecum was not photographed.'):
            with self.subTest(sentence):
                self.assertNotEqual(extent(PLAIN_HEAD + sentence + ' ' + BX + '\n'), 'cecum')

    def test_the_same_readings_in_a_labelled_paragraph_and_a_findings_section(self):
        """Cycle 2, outcome O5 and O7 in two other layouts: an inline "Colonoscopy:" label and a "Findings:" section read
        the closed form complete and another occasion's reach incomplete, as the procedure heading does."""
        layouts = (REPORT_HEAD + 'Colonoscopy: The colonoscope was advanced to the transverse colon. {} ' + BX + '\n',
                   head('Colonoscopy Report') + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the '
                   'transverse colon. {} ' + BX + '\n')
        for layout in layouts:
            for sentence, reached in (('Cecal intubation was achieved, as confirmed by photographs of the appendiceal '
                                       'orifice.', 'cecum'),
                                      (ANOTHER_OCCASION[0], 'incomplete: transverse colon'),
                                      (ANOTHER_OCCASION[2], 'incomplete: transverse colon')):
                with self.subTest(layout=layout[:60], sentence=sentence):
                    self.assertEqual(extent(layout.format(sentence)), reached)

    def test_each_sentence_is_read_once_and_a_long_one_not_at_all(self):
        """Cycle 2, outcome O8: the cycle-1 reader re-ran its sentence scans for every landmark hit (x1000 hits in one
        sentence: 45.5 s on the cycle-1 head). The grammar reads a sentence at most once, and a sentence longer than
        REACH_STATEMENT_CHARS not at all; the lens's shape stays linear."""
        # three landmark hits per sentence (the cecal intubation, the orifice, the valve): read once, not three times
        many = PLAIN_HEAD + CLOSED_FORMS[2] + ' ' + 'Cecal intubation was achieved, as confirmed by visualization of the ' \
            'appendiceal orifice and the ileocecal valve. ' * 99 + BX + '\n'
        counting = _Counting(detect._REACH_STATEMENT)
        with mock.patch.object(detect, '_REACH_STATEMENT', counting):
            # refutation cycle 3 (cost C3-5): a reach statement is believed only as the text's one landmark word - here
            # a hundred sentences name it, so the extent keeps its base reading (none), as the installed release reads it
            self.assertIsNone(extent(many))
        self.assertGreaterEqual(counting.calls, 100)  # every reach sentence is read ...
        self.assertLessEqual(counting.calls, len(sections.layout(many).sentences))  # ... and none twice
        long_sentence = head('Colonoscopy') + 'Indications: Screening.\nProcedure: The colonoscope was inserted. ' + \
            'Cecal intubation was achieved, ' * 1500 + 'and the examination ended.\n'
        counting = _Counting(detect._REACH_STATEMENT)
        with mock.patch.object(detect, '_REACH_STATEMENT', counting):
            start = time.perf_counter()
            detect.route(long_sentence, DAY)
            took = time.perf_counter() - start
        self.assertEqual(counting.calls, 0)
        self.assertLess(took, 15)  # 1.6 s measured on the builder's tree; the cycle-1 head took 91.9 s


# --- a pronoun's failure ---------------------------------------------------------------------------------------------
ERCP = head('ERCP Report') + 'Procedure: ERCP\nThe duodenoscope was advanced to the second portion of the duodenum. Deep ' \
    'biliary cannulation was achieved. '
BRUSHINGS = 'Biliary brushings were obtained from the stricture'
LISTED_HOT = COLON_HEAD + 'Procedure: Colonoscopy with hot snare polypectomy\n' + ADVANCED + \
    'A 15 mm pedunculated polyp was found in the sigmoid colon. '


def pronoun_reading(sentence):
    """services.predicate_subject's reading of the pronoun subject of the clause after "; " or " but " in ``sentence``,
    read through the clause before it."""
    cut = sentence.index('; ') + 2 if '; ' in sentence else sentence.index(' but ') + 1
    predicate = re.compile(r'\b(?:was|were)\b').search(sentence, cut).start()
    return gi_services.predicate_subject(sentence, cut, predicate, (0, cut))


class PronounTests(SimpleTestCase):
    """Cycle 2, outcome O2: a pronoun is read through the clause before it only by that clause's own main predicate."""

    def test_a_pronouns_abort_after_a_completed_act_is_the_examinations(self):
        """Cycle 2, outcome O2 and its variants: after a brushing that was obtained - whatever attempt word its clause
        holds elsewhere ("after two attempts", "after a failed first pass") and whichever singular pronoun follows - "it
        was then aborted" is the ERCP's abort. The ERCP reads uncertain and 43260 is held, as the installed release
        reads it; the cycle-1 pin (no attempt word) reads the same."""
        for tail in ('; it was then aborted', ' after two attempts; it was then aborted',
                     ' after a failed first pass; it was then aborted', ' after two attempts; this was then aborted',
                     ', which the first brush had been unable to sample; it was then aborted'):
            with self.subTest(tail):
                text = ERCP + BRUSHINGS + tail + ' because of oxygen desaturation.\n'
                self.assertEqual(finding(text, 'gi.ercp').status, 'uncertain')
                brushing = proposals(text, [('43260', BRUSHINGS)])['43260']
                self.assertEqual(label(brushing), 'HELD')
                self.assertIn('performed_status', [c.fact for c in brushing.clarifications])

    def test_a_singular_pronoun_never_stands_for_a_plural_subject(self):
        """Cycle 2, outcome O2 (variant): "Biliary brushings were attempted; it was then aborted ..." - "it" cannot be
        the plural brushings, so the abort is the ERCP's: 43260 (cited on the cannulation) is held, as the installed
        release holds it."""
        text = ERCP + 'Biliary brushings were attempted; it was then aborted because of oxygen desaturation.\n'
        self.assertEqual(finding(text, 'gi.ercp').status, 'uncertain')
        self.assertEqual(label(proposals(text, [('43260', 'Deep biliary cannulation was achieved')])['43260']), 'HELD')

    def test_the_colonoscopy_and_egd_twins_keep_the_incompleteness(self):
        """Cycle 2, outcome O2 (the colonoscopy variant) and an EGD twin: a completed act's clause with "after two
        attempts" lends the pronoun nothing, so "it was then aborted" makes the examination incomplete and keeps the
        "Incomplete procedure" modifier consideration, as the installed release reads it."""
        colon = COLON_HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum. Cold snare polypectomy of ' \
            'a 6 mm polyp in the ascending colon was completed after two attempts; it was then aborted because of oxygen ' \
            'desaturation.\n'
        self.assertEqual(finding(colon, 'gi.colonoscopy').status, 'incomplete')
        polypectomy = proposals(colon, [('45385', 'Cold snare polypectomy of a 6 mm polyp in the ascending colon was '
                                                  'completed')])['45385']
        self.assertIn('service.incomplete', flagged(polypectomy))
        self.assertTrue(incompleteness_considered(polypectomy))
        upper = UPPER_HEAD + 'Procedure: Upper endoscopy\n' + EGD_IN + 'Cold forceps biopsies were obtained from the antrum ' \
            'after two attempts; it was then aborted because of oxygen desaturation.\n'
        self.assertEqual(finding(upper, 'gi.egd').status, 'incomplete')
        biopsy = proposals(upper, [('43239', 'Cold forceps biopsies were obtained from the antrum')])['43239']
        self.assertIn('service.incomplete', flagged(biopsy))
        self.assertTrue(incompleteness_considered(biopsy))

    def test_an_attempts_or_failures_own_clause_names_its_act(self):
        """Cycle 2, outcome O2, the controls: where the clause before the pronoun states the act attempted, its failure
        is that act's own - the examination is not incomplete and the attempted act is held ("Hot snare polypectomy of
        the polyp was attempted; it was unsuccessful."; an EGD balloon dilation twin)."""
        # refutation cycle 3 (outcome C3-1, C3-2): the pronoun rule is abandoned - "it was unsuccessful" is the
        # examination's failure, the base reading (the installed release reads both twins so); the act stays held
        text = LISTED_HOT + 'Hot snare polypectomy of the polyp was attempted; it was unsuccessful.\n'
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')
        self.assertEqual(label(proposals(text, [('45385', 'Colonoscopy with hot snare polypectomy')])['45385']), 'HELD')
        upper = UPPER_HEAD + 'Procedure: Upper endoscopy with balloon dilation\n' + EGD_IN + 'Balloon dilation of the ' \
            'stricture was attempted; it was unsuccessful.\n'
        self.assertEqual(finding(upper, 'gi.egd').status, 'incomplete')
        self.assertEqual(label(proposals(upper, [('43249', 'Balloon dilation of the stricture was attempted')])['43249']),
                         'HELD')

    def test_the_antecedents_own_main_predicate_decides(self):
        """Refutation cycle 3 (outcome C3-1, C3-2): services.predicate_subject never reads a pronoun through the clause
        before it - cycle 2's closed form read only the antecedent's first verb group, so a clause that went on to say
        the act succeeded ("... failed with a balloon and was achieved with a basket; it was then aborted") lent it the
        examination's abort. Every pronoun stays unresolved: the base reading."""
        for sentence in ('Hot snare polypectomy was attempted; it was unsuccessful.',
                         'Hot snare polypectomy failed; it was abandoned.',
                         'The polypectomy was attempted but it was unsuccessful.',
                         'Stone extraction failed with a balloon and was achieved with a basket; it was then aborted.',
                         'Brushing of the stricture was attempted and was successful; it was then aborted.',
                         'Biliary brushings were obtained from the stricture after two attempts; it was then aborted.'):
            with self.subTest(sentence):
                self.assertTrue(pronoun_reading(sentence).pronoun)

# --- one failure vocabulary ------------------------------------------------------------------------------------------
LISTED_COLD = COLON_HEAD + 'Procedure: Colonoscopy with cold snare polypectomy\n' + ADVANCED + \
    'A 7 mm sessile polyp was found in the transverse colon.\n'


class FailureVocabularyTests(SimpleTestCase):
    """Cycle 2, outcome O6: routing's subject-tested failure cues and the services reader read one failure vocabulary."""

    def test_a_listed_acts_stated_stop_holds_it(self):
        """Cycle 2, outcome O6 and its variants: routing reads "halted", "stopped because/due/before/at/short" and
        "precluded" as the polypectomy's own failure, so the examination is complete; the services reader now reads the
        same words, so the procedure line never makes the halted polypectomy done: 45385 is held, never READY."""
        for word in ('halted because of bleeding', 'stopped because of bleeding', 'precluded by its position',
                     'stopped due to bleeding', 'stopped before completion', 'stopped at the patient’s request',
                     'stopped short'):
            with self.subTest(word):
                text = LISTED_COLD + 'The polypectomy was ' + word + '.\n'
                self.assertEqual(label(proposals(text, [('45385', 'Colonoscopy with cold snare polypectomy')])['45385']),
                                 'HELD')

    def test_the_pinned_failures_stay_held(self):
        """Cycle 2, outcome O6, the cycle-1 pins (acts F1): "aborted", "discontinued" and "terminated" stay held."""
        for word in ('aborted', 'discontinued', 'terminated'):
            with self.subTest(word):
                text = LISTED_COLD + 'The polypectomy was ' + word + '.\n'
                self.assertEqual(label(proposals(text, [('45385', 'Colonoscopy with cold snare polypectomy')])['45385']),
                                 'HELD')

    def test_the_egd_and_ercp_twins(self):
        """Cycle 2, outcome O6 in other families, re-read in cycle 3: an EGD biopsy, an EGD balloon dilation and an
        ERCP sphincterotomy each listed and then stated halted, stopped because of bleeding or precluded read READY
        with the installed incompleteness warning (the services reader no longer reads those words; routing keeps them
        the examination's); the gastric polypectomy beside a polyp only found is withheld by the listing rule;
        "completed" is READY with no warning."""
        shapes = (
            (UPPER_HEAD + 'Procedure: Upper endoscopy with cold forceps biopsy\n' + EGD_IN + 'An area of erythema was found '
             'in the gastric antrum.\nThe biopsy was {}.\n', '43239', 'Upper endoscopy with cold forceps biopsy'),
            (UPPER_HEAD + 'Procedure: Upper endoscopy with balloon dilation\n' + EGD_IN + 'A benign-appearing stricture was '
             'found at 30 cm.\nBalloon dilation of the stricture was {}.\n', '43249', 'Upper endoscopy with balloon dilation'),
            (UPPER_HEAD + 'Procedure: Upper endoscopy with snare polypectomy\n' + EGD_IN + 'A 12 mm polyp was found in the '
             'gastric body.\nThe polypectomy was {}.\n', '43251', 'Upper endoscopy with snare polypectomy'),
            (ERCP_HEAD + 'Procedure: ERCP with biliary sphincterotomy\nThe duodenoscope was advanced to the second portion '
             'of the duodenum. Deep biliary cannulation was achieved.\nThe sphincterotomy was {}.\n', '43262',
             'ERCP with biliary sphincterotomy'))
        for shape, value, quote in shapes:
            for word in ('halted because of bleeding', 'stopped because of bleeding', 'precluded by the angulation',
                         'completed'):
                with self.subTest(code=value, word=word):
                    item = proposals(shape.format(word), [(value, quote)])[value]
                    if word == 'completed':
                        self.assertEqual((label(item), 'service.incomplete' in flagged(item)), ('READY', False))
                    elif value == '43251':  # the listing rule: the gastric polyp is only found, so no removal stands
                        self.assertEqual(label(item), 'HELD')
                    else:  # refutation cycle 3: the installed release's reading, its incompleteness warning kept
                        self.assertEqual((label(item), 'service.incomplete' in flagged(item)), ('READY', True))

    def test_another_clauses_or_a_medications_stop_leaves_the_act_done(self):
        """Cycle 2, outcome O6, the controls: a medication halted or discontinued, or a stop in another clause or before
        another mention of the act, says nothing about the polypectomy done: 45385 stays READY."""
        for sentence in ('Cold snare polypectomy of the 6 mm sigmoid polyp was performed with apixaban discontinued for '
                         'two days.',
                         'Cold snare polypectomy of the 6 mm sigmoid polyp was performed after apixaban was halted for two '
                         'days.',
                         'Cold snare polypectomy of the 6 mm sigmoid polyp was performed; apixaban had been stopped before '
                         'the procedure.',
                         'Apixaban was stopped before polypectomy, and Cold snare polypectomy of the 6 mm sigmoid polyp was '
                         'performed.'):
            with self.subTest(sentence):
                text = COLON_HEAD + 'Procedure: Colonoscopy\n' + ADVANCED + sentence + '\n'
                self.assertEqual(label(proposals(text, [('45385', 'Cold snare polypectomy of the 6 mm sigmoid polyp')])[
                    '45385']), 'READY')

    def test_both_readers_are_built_from_one_vocabulary(self):
        """Refutation cycle 3 (outcome C3-3, C3-4; cost C3-1): the shared vocabulary is replaced by consumption. Routing's
        subject-tested cues are unchanged (cues.ACT_*); the services reader reads cycle 1's failure words only; and
        routing gives a failure to a sub-act only where the services reader reads that act failed by the same word
        (detect._consumed_by_the_services_reader) - so a stop word the services reader does not read stays the
        examination's, as the installed release reads it."""
        routing = dict(cues.INCOMPLETE_CLAUSE)
        self.assertEqual(routing['terminated'].pattern, r'\b(?:' + '|'.join(cues.ACT_STOPPED) + r')\b')
        self.assertEqual(routing['stopped'].pattern, r'\bstopped\s+(?:' + '|'.join(cues.ACT_STOPPED_HOW) + r')\b')
        self.assertEqual(routing['precluded'].pattern, r'\b' + cues.ACT_PRECLUDED + r'\b')
        for word in ('failed', 'unsuccessful', 'abandoned', 'aborted', 'terminated', 'discontinued'):
            with self.subTest(read=word):
                self.assertIsNotNone(cues.FAILED_ACT.search(f'The polypectomy was {word}.'))
        for phrase in ('halted because of bleeding', 'stopped because of bleeding', 'precluded by the angulation'):
            with self.subTest(not_read=phrase):
                self.assertIsNone(cues.FAILED_ACT.search(f'The polypectomy was {phrase}.'))
                text = LISTED_COLD + f'The polypectomy was {phrase}.\n'
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')
        self.assertIsNone(cues.FAILED_ACT_BEFORE.search('The procedure was aborted after the '))
        self.assertEqual(cues.FAILED_ACT_BEFORE.search('an unsuccessful ').group('w'), 'unsuccessful')
