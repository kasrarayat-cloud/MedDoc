"""DECISIONS D165 (the Gemini migration's round 5g, narrowing only: round5f review:colon5 problems 2-4), SYNTHETIC, each
built from its source's own input. Nothing is sent.

- D165 (1) (review:colon5 problem 2, critical, pre-existing): the role label is read for the act's SENTENCE, not only from
  the line each place it cites begins on. A place that begins mid-sentence (the text from the previous sentence end to
  its start holds more than whitespace, by the engine's own boundary: '.', '!' or '?' followed by whitespace) is read
  from the line its sentence begins on, by D152's and D158's label rules; a place that holds none of the act's words is
  read up to the act's words when they close the sentence it ends in. So a hard-wrapped signed sentence that Gemini cites
  as one passage per line (FRESH-2 C/W1-u31a-reg-p7-codes-025 r1's citation shape) is held as the installed release
  holds it.
- D165 (2) NOT INTEGRATED (round 5g integration; review:colon6 problem 0, critical): reading the physician's own label
  on the act's line as the act's role released holds that 05a881a75 and c2e53f8e keep. Colon5's cost stays recorded:
  the physician-labelled line under a signed line is held another_role (pinned below), where c2e53f8e is READY.
- D165 (3) (problem 4, wording): the lines above the act's own are read nearest first, so the entry named is the
  nearest labelled line's, as c2e53f8e names it.
- D165GuardTheErcpQuestionOfALineWiseSignedAct guards D168 (3): it FAILS on D165 alone, by design.

c2e53f8e's outputs (engine.assess as tests/test_harness_engine.py drives it, on the same texts and codes, with no
participant and with Astra and Fable read and proposing nothing) and e5628be56's, f9013e12e's and 05a881a75's are in each
docstring."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events, wording
from tests.test_interpretation_events import asked, exam, inventory, proposal, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_claims import READ_NOTHING, STONE
from tests.test_interpretation_r5_colon import CECUM_DONE, cexam, creach, document, kept, lesion, nursing_question
from tests.test_interpretation_r5c_colon import Held

POLYP = 'A 6 mm sessile polyp in the sigmoid colon'
SNARE = POLYP + ' was removed with a cold snare.'
CONTINUED = 'was removed with a cold snare.'
SIG = 'Documented by Jo Rowe, RN: '
SIGNATURES = (('Documented by Jo Rowe, RN: ', 'nursing'), ('Per nursing note: ', 'nursing'),
              ('Entered by Jo Rowe, LPN: ', 'nursing'), ('CRNA documented: ', 'anesthesia'))
HEAD = ('Colonoscopy report (fictional)', 'Procedure: Colonoscopy', CECUM_DONE, 'Findings')
# FRESH-2 C/W1-u31a-reg-p7-codes-025 r1's own line-wise citation of a wrapped sentence (its P17 and P18), with a
# signature label put before it (constructed)
P17 = SIG + 'Sigmoid colon, 30 cm: 10 mm sessile polyp, removed en bloc with a cold'
P18 = 'snare and retrieved (jar 3).'


def asks(passage: str, entry: str = 'nursing') -> str:
    """The another-role question over the snare, quoting ``passage`` as reconcile.quote quotes it."""
    return nursing_question('snare removal', wording.quote(passage, 120)[1:-1], entry)


def line_wise(lines, passages: dict, cited_by, cited, *, kind_words: str = 'removed',
              status_words: str = 'was removed with a cold snare', technique: str = 'cold snare',
              lesion_at: str = 'P2', lesion_words: str = '6 mm sessile polyp', head=HEAD) -> tuple:
    """The r5 colon report's head (``head``), then ``lines``; Gemini cites ``passages`` ({id: text}, one passage per
    line as it cites wrapped lines); the cold snare removal (E2) stated in ``cited_by`` (its kind's and status's
    passages), its lesion (L1) in ``lesion_at``; 45385 citing ``cited`` (a phrase or a tuple of phrases)."""
    e2 = act('E2', cited_by[0], 'snare', kind_words, status_words=status_words,
             technique=a('cold_snare', technique, list(cited_by)),
             target=tg('L1', 'sigmoid_colon', lesion_words, [lesion_at]))
    for name in ('kind', 'status'):
        e2[name]['passages'] = list(cited_by)
    inv, text = document(list(head) + list(lines), dict({'P1': CECUM_DONE}, **passages), events=[cexam('P1'), e2],
                         lesions=[lesion('L1', lesion_words, lesion_at, 'sigmoid_colon', 'sigmoid colon', '6 mm')],
                         reach=[creach(passage='P1')])
    return inv, text, [('45385', cited)]


def attested(first: str = P17) -> tuple:
    """P17 / P18 as FRESH-2 C/W1-u31a-reg-p7-codes-025 r1 cites them: kind 'snare' and status 'removed en bloc with a
    cold', each citing both line passages; 45385 citing both."""
    return line_wise([first, P18], {'P2': first, 'P3': P18}, ['P2', 'P3'], (first, P18), kind_words='snare',
                     status_words='removed en bloc with a cold', lesion_words='10 mm sessile polyp')


def wrapped(label: str, cited_by=('P2', 'P3')) -> tuple:
    """The r5 report's wrapped sentence '<label> A 6 mm sessile polyp in the sigmoid colon' / 'was removed with a cold
    snare.' cited as two line passages; the act's kind and status words on the second line."""
    first = label + POLYP
    return line_wise([first, CONTINUED], {'P2': first, 'P3': CONTINUED}, list(cited_by), (first, CONTINUED))


def physician_line(above: str, label: str = 'Endoscopist: ') -> tuple:
    """review:colon5 problem 3: ``above`` / '<the physician's label> <the snare sentence>', cited as one passage."""
    passage = above + '\n' + label + SNARE
    return line_wise([above, label + SNARE], {'P2': passage}, ['P2'], passage)


def no_text(build) -> str:
    """events.evaluate's reason over a Reading with no text (the review overlay's counted codes)."""
    inv, text, codes = build
    return events.evaluate('45385', tuple(span for phrase in ((codes[0][1],) if isinstance(codes[0][1], str)
                                                               else codes[0][1]) for span in kept(text, phrase)),
                           events.Reading.of(inv)).reason


class D165AWrappedSentenceCitedLineByLine(Held):
    """D165 (1), review:colon5 problem 2: the label is read for the act's sentence."""

    def test_d165_a_signed_sentence_cited_as_two_line_passages_is_held(self):
        """review:colon5 problem 2's input: P17 'Documented by Jo Rowe, RN: Sigmoid colon, 30 cm: 10 mm sessile polyp,
        removed en bloc with a cold' and P18 'snare and retrieved (jar 3).', the snare's kind and status each citing
        both, 45385 citing both. c2e53f8e: needs_clarification [performed_status] another_role in both configurations
        (its sentence keeps the wrap). e5628be56, f9013e12e and 05a881a75: READY in both (P18's own line names no
        role). Held here in both, quoting the first passage, as D146 and D158 quote Gemini's passage."""
        for participants in ((), READ_NOTHING):
            self.held(run(*attested(), participants=participants), '45385', asks(P17),
                      participants=len(participants))

    def test_d165_the_r5_reports_wrapped_sentence_cited_line_by_line_is_held(self):
        """The r5 report's wrapped sentence cited as two line passages, for each signature label: the act's kind and
        status passages both lines (the first holds none of its words), or the second line only (45385 citing both).
        c2e53f8e: held another_role in both configurations, naming the same entry. e5628be56, f9013e12e and
        05a881a75: READY."""
        for label, entry in SIGNATURES:
            for cited_by in (('P2', 'P3'), ('P3',)):
                for participants in ((), READ_NOTHING):
                    inv, text, codes = wrapped(label, cited_by)
                    self.held(run(inv, text, codes, participants=participants), '45385',
                              asks((label + POLYP) if cited_by == ('P2', 'P3') else CONTINUED, entry),
                              label=label, cited_by=cited_by, participants=len(participants))

    def test_d165_the_continuation_line_cited_alone_is_held(self):
        """D158's recorded residual (rule 1's own limit): Gemini citing only the continuation line 'was removed with a
        cold snare.' of the wrapped signed sentence, for its kind, its status and 45385. c2e53f8e: held another_role
        in both configurations. e5628be56, f9013e12e and 05a881a75: READY."""
        for label, entry in SIGNATURES:
            first = label + POLYP
            inv, text, codes = line_wise([first, CONTINUED], {'P2': first, 'P3': CONTINUED}, ['P3'], CONTINUED)
            self.held(run(inv, text, codes), '45385', asks(CONTINUED, entry), label=label)

    def test_d165_controls_an_unsigned_wrap_or_a_sentence_that_ended_is_ready(self):
        """Unchanged: P17 / P18 with no signature label; the r5 wrap with no label, cited line by line; and 'Documented
        by Jo Rowe, RN: polyp seen.' / the snare line, the snare line cited alone (the signed sentence ended before
        it). READY on this build, on e5628be56, on f9013e12e, on 05a881a75 and on c2e53f8e."""
        self.ready(run(*attested(P17[len(SIG):])), '45385', shape='P17/P18 unsigned')
        self.ready(run(*wrapped('')), '45385', shape='r5 wrap unsigned')
        inv, text, codes = line_wise([SIG + 'polyp seen.', SNARE], {'P3': SNARE}, ['P3'], SNARE, lesion_at='P3')
        self.ready(run(inv, text, codes), '45385', shape='the signed sentence ended')

    def test_d165_costs_a_signed_line_with_no_sentence_end_above_the_act(self):
        """RECORDED COSTS (constructed; DECISIONS D165): the engine's sentence ends only at '.', '!' or '?' followed by
        whitespace, so a signed line above the act with no sentence end - 'Documented by Jo Rowe, RN:' alone, or
        'Documented by Jo Rowe, RN: patient positioned left lateral' - is in the act's sentence, and the snare line
        cited alone is held. c2e53f8e: READY in both configurations (its _sentences cuts after a label line and before
        a line that opens a sentence). e5628be56, f9013e12e and 05a881a75: READY."""
        for above in ('Documented by Jo Rowe, RN:', 'Documented by Jo Rowe, RN: patient positioned left lateral'):
            inv, text, codes = line_wise([above, SNARE], {'P3': SNARE}, ['P3'], SNARE, lesion_at='P3')
            self.held(run(inv, text, codes), '45385', asks(SNARE), above=above)


class D165ThePhysiciansOwnLabelOnTheActsLine(Held):
    """D165 (2) is NOT integrated (review:colon6 problem 0). review:colon5 problem 3 stays a recorded cost: held
    another_role here, as on 05a881a75, where c2e53f8e, e5628be56 and f9013e12e are READY. These controls stay held
    either way."""

    def test_d165_recorded_cost_the_physicians_label_on_the_acts_line_stays_held(self):
        """review:colon5 problem 3's input: 'Documented by Jo Rowe, RN: patient positioned left lateral.' / 'Endoscopist:
        A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.', cited as one passage. Held another_role
        in both configurations, as 05a881a75 holds it (D158 reads the passage's first line): a hold where c2e53f8e is
        READY, a recorded cost; a release here is a deliberate change."""
        above = 'Documented by Jo Rowe, RN: patient positioned left lateral.'
        for participants in ((), READ_NOTHING):
            self.held(run(*physician_line(above), participants=participants), '45385',
                      asks(above + '\n' + 'Endoscopist: ' + SNARE), above=above, participants=len(participants))

    def test_d165_controls_a_physician_label_the_installed_release_runs_on_into_stays_held(self):
        """Not every physician label opens a sentence for the installed release: under 'Documented by Jo Rowe, RN:
        patient positioned left lateral' (no sentence end), 'endoscopist: <the snare sentence>', '> Endoscopist: ...',
        '· Endoscopist: ...' and 'Endoscopist:<the snare sentence>' (no space after the colon) run on from that line in
        c2e53f8e's _sentences, whose signature label then closes before its act: held in both configurations, as on
        05a881a75. D165 (2) reads the physician's label only in the forms opens_a_field names, so these stay held (READY
        on e5628be56 and f9013e12e)."""
        above = 'Documented by Jo Rowe, RN: patient positioned left lateral'
        for line in ('endoscopist: ' + SNARE, '> Endoscopist: ' + SNARE, '· Endoscopist: ' + SNARE,
                     'Endoscopist:' + SNARE):
            passage = above + '\n' + line
            inv, text, codes = line_wise([above, line], {'P2': passage}, ['P2'], passage)
            self.held(run(inv, text, codes), '45385', asks(passage), line=line[:16])

    def test_d165_controls_a_signature_closed_before_the_act_on_its_own_line_still_holds(self):
        """D146 (reading 5) unchanged: the act's line 'Endoscopist: see below. Documented by Jo Rowe, RN: <the snare
        sentence>' under the signed line, cited as one passage, is held naming the nursing entry. c2e53f8e, f9013e12e
        and 05a881a75: held another_role. e5628be56: READY."""
        above = 'Documented by Jo Rowe, RN: patient positioned left lateral.'
        passage = above + '\nEndoscopist: see below. ' + SIG + SNARE
        inv, text, codes = line_wise([above, 'Endoscopist: see below. ' + SIG + SNARE], {'P2': passage}, ['P2'],
                                     passage)
        self.held(run(inv, text, codes), '45385', asks(passage))

    def test_d165_controls_the_physicians_line_wrapped_before_the_acts_words_still_holds(self):
        """A RECORDED COST, unchanged (constructed): the signed line, then 'Endoscopist: A 6 mm sessile polyp in the
        sigmoid colon' / 'was removed with a cold snare.', cited as one passage. The act's own words stand on the
        continuation line, which no physician label opens, so D165 (2) does not apply and D158 holds it, as 05a881a75
        does. c2e53f8e, e5628be56 and f9013e12e: READY."""
        above = 'Documented by Jo Rowe, RN: patient positioned left lateral.'
        passage = above + '\nEndoscopist: ' + POLYP + '\n' + CONTINUED
        inv, text, codes = line_wise([above, 'Endoscopist: ' + POLYP, CONTINUED], {'P2': passage}, ['P2'], passage)
        self.held(run(inv, text, codes), '45385', asks(passage))


K6C = 'CRNA charted the sedation:\n' + SIG + POLYP + '\n' + CONTINUED  # colon4's K6c
K6H = 'CRNA charted the sedation:\nDocumented by Jo Rowe, RN:\n' + SNARE  # colon5's K6h


class D165TheNearestLabelledLineNamesTheEntry(Held):
    """D165 (3), review:colon5 problem 4: wording only - the entry named, never whether one is."""

    def test_d165_the_nearest_labelled_line_names_the_entry(self):
        """K6c ('CRNA charted the sedation:' / 'Documented by Jo Rowe, RN: A 6 mm ...' / 'was removed with a cold
        snare.') and K6h ('CRNA charted the sedation:' / 'Documented by Jo Rowe, RN:' / the snare line), each cited as
        one passage: held naming the NURSING entry. 05a881a75: held naming the anesthesia entry (both signatures in one
        label). c2e53f8e: K6c held naming nursing; K6h READY (a cost recorded in D158). e5628be56 and f9013e12e:
        READY."""
        for passage in (K6C, K6H):
            for participants in ((), READ_NOTHING):
                inv, text, codes = line_wise([passage], {'P2': passage}, ['P2'], passage)
                self.held(run(inv, text, codes, participants=participants), '45385', asks(passage, 'nursing'),
                          passage=passage[:40], participants=len(participants))

    def test_d165_controls_anesthesia_nearer_or_a_label_spanning_lines(self):
        """'Documented by Jo Rowe, RN: propofol given' / 'CRNA charted the sedation:' / the snare line names the
        anesthesia entry, the nearer label's (05a881a75 the same). 'Documented by' / 'Jo Rowe, RN: <the snare
        sentence>' (K8: ROLE_SIGNATURE's \\s+ after 'by' takes the line break) is still held naming nursing: the whole
        label is read where no single line names a role. c2e53f8e: READY on both (costs recorded in D158)."""
        nearer = 'Documented by Jo Rowe, RN: propofol given\nCRNA charted the sedation:\n' + SNARE
        spanning = 'Documented by\nJo Rowe, RN: ' + SNARE
        for passage, entry in ((nearer, 'anesthesia'), (spanning, 'nursing')):
            inv, text, codes = line_wise([passage], {'P2': passage}, ['P2'], passage)
            self.held(run(inv, text, codes), '45385', asks(passage, entry), passage=passage[:30])


class D165TheRivalOfALineWiseSignedExtraction(SimpleTestCase):
    """A guard for D163 on D165 (1)'s new holds: a code another_role_hold holds keeps its acts as claims, so its rival
    for the same act keeps its competing_codes hold."""

    def test_d165_the_rival_of_a_line_wise_signed_extraction_keeps_its_competition(self):
        """Finding 5's stone clearance (tests.test_interpretation_r3_claims.STONE) with the extraction 'Documented by Jo
        Rowe, RN: The stone fragments from the bile duct' / 'were extracted with an extraction balloon.' cited as two
        line passages; 43264 citing both, 43265 the lithotripsy. e5628be56, f9013e12e and 05a881a75: both held
        [competing_codes]. Here: 43265 held [competing_codes], 43264 [competing_codes, performed_status]. c2e53f8e with
        Astra and Fable read and proposing nothing: 43264 held [competing_codes]."""
        first, second = SIG + 'The stone fragments from the bile duct', 'were extracted with an extraction balloon.'
        lines = {'P1': STONE['P1'], 'P2': STONE['P2'], 'P3': STONE['P3'], 'P4': first, 'P5': second}
        extraction = act('E4', 'P5', 'stone_extraction', 'extracted', status_words='were extracted',
                         procedure=a('ercp'), target=tg('', 'bile_duct', 'bile duct', ['P4']),
                         technique=a('extraction_balloon', 'extraction balloon', ['P5']))
        for name in ('kind', 'status'):
            extraction[name]['passages'] = ['P4', 'P5']
        inv, text = inventory(lines, events=[
            exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
            act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
                target=tg('', 'bile_duct', 'biliary', ['P2']), technique=a('sphincterotome', 'sphincterotome', ['P2'])),
            act('E3', 'P3', 'lithotripsy', 'lithotripsy', status_words='was fragmented', procedure=a('ercp'),
                target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
                technique=a('lithotripter', 'lithotripsy', ['P3'])), extraction])
        for participants in ((), READ_NOTHING):
            result = run(inv, text, [('43264', (first, second)), ('43265', STONE['P3'])], participants=participants)
            with self.subTest(participants=len(participants)):
                self.assertEqual((proposal(result, '43265').status, asked(proposal(result, '43265'))),
                                 ('needs_clarification', ['competing_codes']))
                self.assertEqual(sorted(asked(proposal(result, '43264'))), ['competing_codes', 'performed_status'])


EXCHANGE = {'P1': 'Procedure: ERCP with biliary stent exchange.',
            'P2': 'The duodenoscope was advanced to the major papilla.',
            'P3': 'The existing biliary stent was removed with a snare.',
            'P4': 'Deep biliary cannulation was achieved with a sphincterotome.'}
PLACED = (SIG + 'A new 10 Fr x 9 cm plastic', 'biliary stent was placed into the common bile duct.')
SWEEP = {'P1': 'The duodenoscope was advanced to the major papilla.',
         'P2': 'Deep biliary cannulation was achieved with a sphincterotome.',
         'P3': 'Cholangiogram showed a mildly dilated bile duct without filling defects.',
         'P4': 'A biliary sphincterotomy was performed.'}
SWEPT = (SIG + 'The bile duct', 'was swept several times with an extraction balloon; no stones or sludge were retrieved.')


def line_wise_ercp(lines: dict, act_event: dict, earlier: list) -> tuple:
    """An ERCP report whose last sentence is signed and hard-wrapped, cited as two line passages (P5, P6): its act's
    kind and status cite both."""
    for name in ('kind', 'status'):
        act_event[name]['passages'] = ['P5', 'P6']
    return inventory(lines, events=[exam('E1', 'P2' if 'stent' in lines['P1'] else 'P1', words='duodenoscope',
                                         procedure=a('ercp')), *earlier, act_event],
                     reach=[{'event': 'E1', 'landmark': 'ampulla', 'words': 'major papilla',
                             'passages': ['P2' if 'stent' in lines['P1'] else 'P1'], 'completion': a('not_stated')}])


class D165GuardTheErcpQuestionOfALineWiseSignedAct(SimpleTestCase):
    """A GUARD for DECISIONS D168 (3) (review:colon5 problem 0, round 5g's ercp7) on D165 (1)'s new holds. It FAILS on
    D165 alone, by design: another_role_hold decides before ercp.ruled, which turns only a READY evaluation into D105's
    exchange hold or D106's nothing-retrieved hold, so the new another_role hold replaces the ERCP question that
    05a881a75, f9013e12e and e5628be56 ask (the fact label stays performed_status). It passes once D168 (3) asks the
    ERCP question as the held code's second clarification."""

    def test_d165_guard_the_exchange_question_of_a_line_wise_signed_stent_placement(self):
        """Finding 22's document (tests.test_interpretation_r4_ercp.EXCHANGE) with the placement 'Documented by Jo
        Rowe, RN: A new 10 Fr x 9 cm plastic' / 'biliary stent was placed into the common bile duct.' cited as two line
        passages, 43274 citing both. 05a881a75, f9013e12e and e5628be56: held [performed_status] possible_exchange,
        asking whether the removal and the placement are one stent exchange (43276). c2e53f8e: READY."""
        lines = dict(EXCHANGE, P5=PLACED[0], P6=PLACED[1])
        placement = act('E4', 'P6', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                        technique=a('stent', 'plastic', ['P5']),
                        target=tg('', 'common_bile_duct', 'common bile duct', ['P6']))
        removal = act('E2', 'P3', 'stent_removal', 'removed', status_words='was removed with a snare',
                      procedure=a('ercp'), technique=a('snare', 'snare', ['P3']),
                      target=tg('', 'bile_duct', 'biliary', ['P3']))
        cannulation = act('E3', 'P4', 'cannulation', 'Deep biliary cannulation', status_words='was achieved',
                          procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P4']),
                          technique=a('sphincterotome', 'sphincterotome', ['P4']))
        inv, text = line_wise_ercp(lines, placement, [removal, cannulation])
        p = proposal(run(inv, text, [('43274', PLACED)]), '43274')
        self.assertTrue(any('one stent exchange (43276)' in c.question for c in p.clarifications),
                        [c.question for c in p.clarifications])

    def test_d165_guard_the_nothing_retrieved_question_of_a_line_wise_signed_sweep(self):
        """Finding 25's sweep (tests.test_interpretation_r4_ercp.SWEEP) with 'Documented by Jo Rowe, RN: The bile duct'
        / 'was swept several times with an extraction balloon; no stones or sludge were retrieved.' cited as two line
        passages, 43264 citing both. 05a881a75, f9013e12e and e5628be56: held [performed_status] nothing_retrieved,
        asking whether any stone, calculus, debris or sludge was removed. c2e53f8e: held readings_disagree."""
        lines = dict(SWEEP, P5=SWEPT[0], P6=SWEPT[1])
        sweep = act('E4', 'P6', 'stone_extraction', 'swept several times with an extraction balloon',
                    status_words='was swept several times', procedure=a('ercp'),
                    target=tg('', 'bile_duct', 'bile duct', ['P5']),
                    technique=a('extraction_balloon', 'extraction balloon', ['P6']))
        cannulation = act('E2', 'P2', 'cannulation', 'Deep biliary cannulation', status_words='was achieved',
                          procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P2']))
        sphincterotomy = act('E3', 'P4', 'sphincterotomy', 'biliary sphincterotomy', status_words='was performed',
                             procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P4']))
        inv, text = line_wise_ercp(lines, sweep, [cannulation, sphincterotomy])
        p = proposal(run(inv, text, [('43264', SWEPT)]), '43264')
        self.assertTrue(any('Was any stone, calculus, debris or sludge removed' in c.question
                            for c in p.clarifications), [c.question for c in p.clarifications])
