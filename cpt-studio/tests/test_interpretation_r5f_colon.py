"""DECISIONS D158 (the Gemini migration's round 5f, narrowing only: D152's two rules, built and held back in round 5e,
and colon4's K6; round5d review:colon3 problems 0-1, round5e review:colon4 problems 1-2), SYNTHETIC, each built from
its source's own input. Nothing is sent.

- D158 (1) (D152 (1) as round 5e built it): a signature label is read from the start of the line on which the act's
  passage begins, up to the last colon before the act's own words, with ROLE_SIGNATURE's reaches - its [^.\\n] reaches
  cross no period and no line break, the space after 'by' or 'nursing' (\\s+) may hold one - on the text path and on
  the passage alone (a Reading with no text). A sentence hard-wrapped before the act's words is held as the one-line
  sentence is.
- D158 (2) (D152 (2)): kind or status words that open at a label are read after the last colon inside them, so the
  label before that colon is read as the installed release reads the label before its own act mention.
- D158 (3) (colon4's K6): the label on the act's own line is read first, as before; only where it names no role is the
  label read from the passage's first line. A label on a line above never renames the role the act's line names.

A code another_role_hold holds supports nothing (assess._claims), so these rules ALONE let a rival code that competed
with the held one for the same act lose its competing_codes hold (round5e/colon4's STOP; the class D163 closes in
assess._claims). tests.test_interpretation_r5e_colon pins the stone-clearance rival; TheRivalOfASignedDilation below
pins the second member the colon4 review found (problem 2). Both FAIL on D158 alone, by design, and pass with D163's
claims (measured with round5e/colon4/experiment-claims.diff).
c2e53f8e's outputs (engine.assess as tests/test_harness_engine.py drives it, on the same texts and codes, with no
participant and with Astra and Fable read and proposing nothing) and e5628be56's and f9013e12e's are in each
docstring."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events, wording
from tests.test_interpretation_events import asked, exam, inventory, proposal, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_claims import READ_NOTHING
from tests.test_interpretation_r5_colon import CECUM_DONE, cexam, creach, document, kept, lesion, nursing_question
from tests.test_interpretation_r5c_colon import Held

POLYP = 'A 6 mm sessile polyp in the sigmoid colon'
SNARE = POLYP + ' was removed with a cold snare.'
WRAP = POLYP + '\nwas removed with a cold snare.'  # the sentence hard-wrapped before its act's own words
SIGNATURES = (('Documented by Jo Rowe, RN: ', 'nursing'), ('Per nursing note: ', 'nursing'),
              ('Entered by Jo Rowe, LPN: ', 'nursing'), ('CRNA documented: ', 'anesthesia'))
PHYSICIAN = 'Endoscopist: see below. Documented by Jo Rowe, RN: ' + WRAP
ONE = 'Documented by Jo Rowe, RN: ' + SNARE
OPENING = 'Documented by Jo Rowe, RN: ' + POLYP + ' was removed'  # problem 1's status words


def asks(passage: str, entry: str = 'nursing') -> str:
    """c2e53f8e's another-role question over the snare, its passage quoted as reconcile.quote quotes it (whitespace runs
    one space, cut at 120 characters): the hard-wrapped sentence's quote is the one-line sentence's."""
    return nursing_question('snare removal', wording.quote(passage, 120)[1:-1], entry)


def cited_on(line: str, passage: str, *, kind_words: str = 'removed',
             status_words: str = 'was removed with a cold snare') -> tuple:
    """The r5 colon report ('Colonoscopy report (fictional)' / 'Procedure: Colonoscopy' / CECUM_DONE / 'Findings' /
    ``line``, which may hold line breaks), the cold snare removal (E2: csnare's event, its kind and status words given)
    citing ``passage``, 45385 citing it."""
    lines = ['Colonoscopy report (fictional)', 'Procedure: Colonoscopy', CECUM_DONE, 'Findings', line]
    e2 = act('E2', 'P2', 'snare', kind_words, status_words=status_words,
             technique=a('cold_snare', 'cold snare', ['P2']),
             target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P2']))
    inv, text = document(lines, {'P1': CECUM_DONE, 'P2': passage}, events=[cexam('P1'), e2],
                         lesions=[lesion('L1', '6 mm sessile polyp', 'P2', 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', passage)]


def no_text(test, line: str, passage: str, question: str = '', **words) -> None:
    """events.evaluate over a Reading with no text (the review overlay's counted codes): held another_role (and, given
    ``question``, asking it word for word)."""
    inv, text, _ = cited_on(line, passage, **words)
    evaluation = events.evaluate('45385', kept(text, passage), events.Reading.of(inv))
    with test.subTest(path='no text', passage=passage[:40]):
        test.assertEqual(evaluation.reason, events.ANOTHER_ROLE)
        test.assertEqual(set(evaluation.supporting) | set(evaluation.read), {'E2'})
        if question:
            test.assertEqual(evaluation.question.question, question)


class AWrappedSignatureLabelHoldsItsAct(Held):
    """D158 (1), round5d review:colon3 problem 0: the label is read from the line on which the passage begins."""

    def test_d158_a_signature_sentence_hard_wrapped_before_its_act(self):
        """The review's shape: 'Findings' / '<label> A 6 mm sessile polyp in the sigmoid colon' / 'was removed with a
        cold snare.', cited whole (kind 'removed' and status 'was removed with a cold snare' on the second line), for
        'Documented by Jo Rowe, RN:', 'Per nursing note:', 'Entered by Jo Rowe, LPN:' and 'CRNA documented:'.
        c2e53f8e: all four needs_clarification [performed_status] another_role in both configurations, this question
        word for word (its _sentences keeps the wrap). e5628be56 and f9013e12e: all four READY (supported)."""
        for label, entry in SIGNATURES:
            inv, text, codes = cited_on(label + WRAP, label + WRAP)
            self.held(run(inv, text, codes), '45385', asks(label + WRAP, entry), label=label)

    def test_d158_the_physicians_line_hard_wrapped(self):
        """'Endoscopist: see below. Documented by Jo Rowe, RN: A 6 mm ...' / 'was removed with a cold snare.', the snare
        citing the signed sentence (c2e53f8e's question word for word), the whole two lines, or the sentence after the
        signature label (held, quoting Gemini's passage where c2e53f8e quotes its own sentence, as D146 records for the
        one-line form). c2e53f8e: all three held [performed_status] another_role. e5628be56 and f9013e12e: READY."""
        for passage in ('Documented by Jo Rowe, RN: ' + WRAP, PHYSICIAN, WRAP):
            inv, text, codes = cited_on(PHYSICIAN, passage)
            self.held(run(inv, text, codes), '45385', asks(passage), passage=passage[:30])

    def test_d158_a_reading_without_the_text_reads_the_whole_passage(self):
        """The same passages through events.evaluate over Reading.of(inv) (no text): the four wrapped sentences and the
        physician's two lines are held another_role. e5628be56 and f9013e12e: supported."""
        for label, _ in SIGNATURES:
            no_text(self, label + WRAP, label + WRAP)
        no_text(self, PHYSICIAN, PHYSICIAN)

    def test_d158_the_space_after_by_or_nursing_may_hold_a_line_break(self):
        """ROLE_SIGNATURE's \\s+ after 'by' and after 'nursing' takes a line break: 'Documented by' / 'Jo Rowe, RN: <the
        snare sentence>' and 'Per nursing' / 'note: <the snare sentence>', cited whole, are held. c2e53f8e: READY on
        both in both configurations (its _sentences cuts at the break: the act's sentence opens at 'Jo Rowe' or
        'note:'), a cost recorded in DECISIONS D158 (colon4's K8 and K8d). e5628be56 and f9013e12e: READY."""
        for line in ('Documented by\nJo Rowe, RN: ' + SNARE, 'Per nursing\nnote: ' + SNARE):
            inv, text, codes = cited_on(line, line)
            self.held(run(inv, text, codes), '45385', asks(line), line=line[:20])

    def test_d158_controls_no_other_reach_crosses_a_line_break(self):
        """ROLE_SIGNATURE's [^.\\n] reaches take no line break: 'Documented' / 'by Jo Rowe, RN: ...', 'Documented by
        Jo' / 'Rowe, RN: ...' and 'CRNA' / 'documented: ...', cited whole, are READY on this build, on e5628be56, on
        f9013e12e and on c2e53f8e."""
        for line in ('Documented\nby Jo Rowe, RN: ' + SNARE, 'Documented by Jo\nRowe, RN: ' + SNARE,
                     'CRNA\ndocumented: ' + SNARE):
            inv, text, codes = cited_on(line, line)
            self.ready(run(inv, text, codes), '45385', line=line[:20])

    def test_d158_controls_as_before(self):
        """Unchanged: the one-line sentence and the wrap after 'was removed with a' (the act's words on the first line)
        held, the question word for word, on this build, on f9013e12e and on c2e53f8e (READY on e5628be56); 'Nurse:'
        wrapped held on all four engines (label_of reads the passage); the wrapped sentence with no label READY on all
        four."""
        for label, entry in SIGNATURES:
            for line in (label + SNARE, label + POLYP + ' was removed with a\ncold snare.'):
                inv, text, codes = cited_on(line, line)
                self.held(run(inv, text, codes), '45385', asks(line, entry), line=line[:30])
        inv, text, codes = cited_on('Nurse: ' + WRAP, 'Nurse: ' + WRAP)
        self.held(run(inv, text, codes), '45385', asks('Nurse: ' + WRAP), line='Nurse:')
        inv, text, codes = cited_on(WRAP, WRAP)
        self.ready(run(inv, text, codes), '45385', line='no label')


EGD_LINE = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
BIOPSIES = ('Biopsies, cold forceps: antrum and body for H. pylori (jar 1); duodenal\nbulb and second portion for '
            'celiac disease (jar 2).')  # FRESH-2 C/W1S-438 r1's P9


def biopsies(kind_words: str = 'Biopsies', status_words: str = 'Biopsies, cold forceps: antrum and body') -> tuple:
    """W1S-438 E7's attested shape: an EGD's biopsy line whose label names the act itself, its status words opening at
    that label; 43239 citing it."""
    lines = {'G1': EGD_LINE, 'G2': 'Findings', 'G3': BIOPSIES}
    biopsy = act('E2', 'G3', 'biopsy', kind_words, status_words=status_words, procedure=a('egd'),
                 technique=a('cold_forceps', 'cold forceps', ['G3']), target=tg('', 'gastric_antrum', 'antrum', ['G3']))
    inv, text = inventory(lines, events=[exam('E1', 'G1', words='gastroscope', procedure=a('egd')), biopsy],
                          reach=[{'event': 'E1', 'landmark': 'second_portion_duodenum',
                                  'words': 'second portion of the duodenum', 'passages': ['G1'],
                                  'completion': a('not_stated')}])
    return inv, text, [('43239', BIOPSIES)]


class WordsOpeningAtTheLabel(Held):
    """D158 (2), round5d review:colon3 problem 1: words that open at a label are read after the colon inside them."""

    def test_d158_status_or_kind_words_opening_at_the_signature_label(self):
        """The review's input: 'Findings' / 'Documented by Jo Rowe, RN: A 6 mm sessile polyp in the sigmoid colon was
        removed with a cold snare.', the status words 'Documented by Jo Rowe, RN: A 6 mm sessile polyp in the sigmoid
        colon was removed' (kind 'removed'); and the same words given as the kind's (status 'was removed'). c2e53f8e:
        both held [performed_status] another_role, this question word for word (its label ends at the last colon before
        its own act mention). e5628be56 and f9013e12e: READY (no label before the words' start)."""
        for words in (dict(status_words=OPENING), dict(kind_words=OPENING, status_words='was removed')):
            inv, text, codes = cited_on(ONE, ONE, **words)
            self.held(run(inv, text, codes), '45385', asks(ONE), words=sorted(words)[0])
        no_text(self, ONE, ONE, status_words=OPENING)

    def test_d158_controls_a_label_that_names_the_act_is_no_role(self):
        """W1S-438 E7's shape (kind 'Biopsies', status words 'Biopsies, cold forceps: antrum and body', the line wrapped
        after 'duodenal'), and the same with the status words as the kind's: 43239 READY on this build, on e5628be56, on
        f9013e12e and on c2e53f8e (the label 'Biopsies, cold forceps' holds no signature)."""
        for words in ({}, dict(kind_words='Biopsies, cold forceps: antrum and body')):
            inv, text, codes = biopsies(**words)
            self.ready(run(inv, text, codes), '43239', words=str(words))


K6 = 'CRNA charted the sedation:\nDocumented by Jo Rowe, RN: ' + SNARE  # colon4's K6
K6B = 'CRNA documented:\nPer nursing note: ' + SNARE
K6D = 'CRNA charted the sedation and\nDocumented by Jo Rowe, RN: ' + SNARE  # the line above has no colon of its own


class TheActsOwnLineNamesItsEntry(Held):
    """D158 (3), colon4's K6: a label on a line above the act's own line never renames the role that line names."""

    def test_d158_a_label_line_above_does_not_rename_the_acts_own_label(self):
        """'CRNA charted the sedation:' / 'Documented by Jo Rowe, RN: <the snare sentence>' (K6) and 'CRNA documented:'
        / 'Per nursing note: <the snare sentence>', each cited as one passage: held, the NURSING entry named, on the
        text path and with no text. f9013e12e: the same question word for word (it reads the act's line). c2e53f8e:
        held naming the nursing entry in both configurations (its sentence begins after the line a colon ends; it
        quotes its own sentence). D152 (1) alone (round5e/colon4/patch-heldback.diff): the anesthesia entry - both
        roles' signatures in one label. e5628be56: READY."""
        for passage in (K6, K6B):
            inv, text, codes = cited_on(passage, passage)
            self.held(run(inv, text, codes), '45385', asks(passage, 'nursing'), passage=passage[:20])
            no_text(self, passage, passage, asks(passage, 'nursing'))

    def test_d158_the_acts_own_line_keeps_its_role_whatever_stands_above(self):
        """'CRNA charted the sedation and' / 'Documented by Jo Rowe, RN: <the snare sentence>', cited as one passage:
        held naming the nursing entry, as f9013e12e names it, word for word. c2e53f8e names the anesthesia entry (its
        sentence keeps the wrap, so both signatures stand in its label: its last match); D152 (1) alone names
        anesthesia too. e5628be56: READY. Constructed; recorded in DECISIONS D158."""
        inv, text, codes = cited_on(K6D, K6D)
        self.held(run(inv, text, codes), '45385', asks(K6D, 'nursing'))

    def test_d158_controls_anesthesia_on_the_acts_line_or_both_in_one_label(self):
        """'Documented by Jo Rowe, RN:' / 'CRNA documented: <the snare sentence>' (anesthesia on the act's own line) and
        'CRNA charted the sedation; documented by Jo Rowe, RN: <the snare sentence>' (both on the act's line): held
        naming the ANESTHESIA entry on this build, on f9013e12e and on c2e53f8e (the installed release's last match).
        e5628be56: READY."""
        for passage in ('Documented by Jo Rowe, RN:\nCRNA documented: ' + SNARE,
                        'CRNA charted the sedation; documented by Jo Rowe, RN: ' + SNARE):
            inv, text, codes = cited_on(passage, passage)
            self.held(run(inv, text, codes), '45385', asks(passage, 'anesthesia'), passage=passage[:20])

    def test_d158_where_the_acts_line_names_no_role_the_passages_first_line_is_read(self):
        """'CRNA charted the sedation:' / 'Documented by Jo Rowe, RN: A 6 mm sessile polyp in the sigmoid colon' / 'was
        removed with a cold snare.', cited whole (the act's own line holds no colon): held [performed_status]
        another_role, as c2e53f8e holds it. f9013e12e and e5628be56: READY. The entry this build names is the
        anesthesia one, where c2e53f8e names nursing: a recorded residual of D158 (wording only)."""
        passage = 'CRNA charted the sedation:\nDocumented by Jo Rowe, RN: ' + WRAP
        inv, text, codes = cited_on(passage, passage)
        p = proposal(run(inv, text, codes), '45385')
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['performed_status'], events.ANOTHER_ROLE))


STRICTURE_LINE = 'A benign-appearing peptic stricture was seen in the distal esophagus at 37 cm.'
WRAPPED_DILATION = 'Documented by Jo Rowe, RN: The stricture\nwas dilated with a through-the-scope balloon to 15 mm.'


def one_dilation(line: str) -> tuple:
    """The colon4 review's problem 2 (round5e/review-colon4/tools/probe_new.py one_dilation): an EGD to the second
    portion (E1), the peptic stricture (L1) and one balloon dilation told on ``line`` (E2, P7); 43249 and 43214 (both
    balloon dilation codes) citing it."""
    lines = {'H1': 'EGD report (fictional)', 'H2': 'Procedure: EGD',
             'P1': 'The gastroscope was advanced to the second portion of the duodenum.', 'P6': STRICTURE_LINE,
             'P7': line}
    inv, text = inventory(lines, events=[
        exam('E1', 'P1', words='gastroscope', procedure=a('egd')),
        act('E2', 'P7', 'dilation', 'dilated', status_words='was dilated', procedure=a('egd'),
            technique=a('balloon', 'through-the-scope balloon', ['P7']),
            target=tg('L1', 'distal_esophagus', 'The stricture', ['P7']))],
        lesions=[les('L1', 'benign-appearing peptic stricture', 'P6', landmark='distal_esophagus',
                     site_words='distal esophagus')],
        reach=[{'event': 'E1', 'landmark': 'second_portion_duodenum', 'words': 'second portion of the duodenum',
                'passages': ['P1'], 'completion': a('not_stated')}])
    return inv, text, [('43249', line), ('43214', line)]


class TheRivalOfASignedDilation(SimpleTestCase):
    """The second member of round5e's rival class (review:colon4 problem 2). FAILS on D158 alone, by design: a code
    another_role_hold holds supports nothing and claims nothing, so the competition between the two codes for the one
    dilation is dropped. Passes with D163 (a held code keeps its acts as claims; measured with
    round5e/colon4/experiment-claims.diff: both codes [performed_status, competing_codes])."""

    def test_d158_two_codes_for_one_signed_wrapped_dilation_keep_their_competition(self):
        """'Documented by Jo Rowe, RN: The stricture' / 'was dilated with a through-the-scope balloon to 15 mm.', 43249
        and 43214 citing it. e5628be56 and f9013e12e: both held [competing_codes] in both configurations. D158 alone:
        both held [performed_status] another_role, competing_codes dropped. c2e53f8e: both held [performed_status]
        another_role in both configurations."""
        for participants in ((), READ_NOTHING):
            result = run(*one_dilation(WRAPPED_DILATION), participants=participants)
            for code in ('43249', '43214'):
                p = proposal(result, code)
                with self.subTest(participants=len(participants), code=code):
                    self.assertEqual(p.status, 'needs_clarification')
                    self.assertIn('competing_codes', asked(p))
