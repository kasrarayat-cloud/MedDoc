"""DECISIONS D143 (the Gemini migration's round-5c repair "questions3"; the review of round 5's "questions2" patch,
problems 0, 1 and 2, and the review of round 5b's "currency2" patch, problems 0 and 3): what a held code's
statement_scope question asks about, and what the member's details row shows beside it.

- (1) The member's details row (answers._passages_of, through validation.questions.question_passages) showed at most
  PER_SOURCE (2) of CPT Studio's own passages, so a question about three statements - finding 3's framed and device
  denials beside C1CL3-001's prior-segment denial - or about a hard-wrapped denial beside another showed the question's
  first statements and never the TARGET denial. A question about several statements now names each passage's statement
  (events._h3_shown), and its row shows one passage of each statement, then the act's, before a second passage of any,
  in the source's order (questions._statements_kept). A source that names no statement, and every other question's
  row, is read as before.
- (2) D126 (4) asked which technique was used where a denial's device and the act's are both verified ("removed with a
  snare" beside "No cold snare was used for the 6 mm sessile polyp."): the contradiction is asked again, as d353e64df
  asked it (statement_scope). The installed release asks conflict:snare there.
- (3) A denial whose scope words do not locate in its passages (FRESH-1 C2MEM-031 r3 E17) was quoted by its status
  words' one wrapped line: it is quoted with its scope's own passages whole, joined across the wrap.
- (4) A denial's relation D128 leaves UNRESOLVED(time) beside a doubt on the same act was displaced by the doubt (h2
  runs before h3): with the member's date equal to the snare's day the code asked performed_status quoting the doubt
  alone, where the installed release asks conflict:snare. The doubt never displaces the same-event contradictions of
  the act it doubts - whether h2 meets it as the act's DOUBT relation or, the doubting sentence listed before the act,
  as that sentence's own uncertain status: the one question asks them and the doubt together
  (events._h3_beside_doubt).
- (5) tests/test_interpretation_r4_currency_pairing.py: a test whose name stated the opposite of its expectation is
  renamed, its docstring corrected (no pin here).

Only questions and the passages shown change: status, bucket, READY and the exclusion are untouched. SYNTHETIC: the
shared S08 builders (tests.test_interpretation_events, tests.test_interpretation_identity) and the round-4 and round-5
builders over fictional documents, in the shapes of the reviews' inputs. Nothing is sent."""
from __future__ import annotations

import itertools
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio import answers
from studio.interpretation import events, normalize
from studio.validation import questions
from tests.test_interpretation_events import (COLONOSCOPE, POLYP, asked, colonoscopy, exam, inventory, proposal,
                                              reached, removed, run)
from tests.test_interpretation_identity import a, accepted, act, sc, tg
from tests.test_interpretation_r3_currency import DATE_LINE, STATED
from tests.test_interpretation_r4_currency_pairing import (DATED_POLYP, DENIAL, conflicts_check, denial_answer,
                                                           stored_relations)
from tests.test_interpretation_r4_questions import (DEVICE, FRAMED, PRIOR, SNARE, SNARE_WORDS, framed, prior,
                                                    relations_of)
from tests.test_interpretation_r5_questions import (BUILD, NO_COLD, SNARE_ONLY, WIDER, Asks, eid_of, no_cold,
                                                    snare_beside)


def row(result, p, text: str) -> list:
    """The texts of the passages the member's details row for ``p``'s question shows (answers._passages_of, as
    answers._rows calls it for the row's one member)."""
    assessment = SimpleNamespace(revision=SimpleNamespace(text=text, pages=[{'start': 0, 'end': len(text), 'page': 1}]),
                                 services=result.services)
    fact = p.clarifications[0].fact
    return [item['text'] for item in answers._passages_of(assessment, [(fact, p.family, p.code)], {p.code: [p]})]


def named(p) -> list:
    """(text, the statement it names) of each of the proposal's source passages."""
    return [(span['text'], span.get(questions.STATEMENT)) for span in p.support['source']]


W_LINES = ('During withdrawal, no polypectomy was performed in the', 'sigmoid colon.')


def wrapped_withdrawal(eid: str, first: str, second: str) -> dict:
    """The review's Input B: S2w hard-wrapped over two lines - its status and time words on the first, its scope and
    target words ('sigmoid colon') on the next; its own time unanchored, UNRESOLVED(time) beside the snare."""
    return act(eid, first, 'removal', 'polypectomy', status='not_performed',
               status_words='no polypectomy was performed', time=a('current_encounter', 'During withdrawal', [first]),
               scope=sc('single_target', 'sigmoid colon', [second]),
               target=tg('', 'sigmoid_colon', 'sigmoid colon', [second]))


# --- D143 (1): every statement the question quotes is in the member's row -------------------------------------------

class D143EveryStatementInTheRow(Asks):
    """questions2 problem 0 (high): the TARGET denial fell out of the member's details row."""

    def test_d143_three_denials_are_all_in_the_members_row_in_every_order(self):
        # Input A: finding 3's framed and device denials (the act's same-site denials) beside C1CL3-001's prior-segment
        # denial (the target denial), each on its own line, in every sentence order. 46e461e7f's row showed the act's
        # passage and the first two statements; the prior-segment sentence was absent in every order
        for names in itertools.permutations(('framed', 'device', 'prior')):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                result = run(inv, text, [('45385', POLYP)])
                p = proposal(result, '45385')
                said = [BUILD[name][1] for name in names if name != 'prior'] + [PRIOR]  # same-site first, then target
                self.assert_asks(p, said)
                self.assertEqual(p.support['question_events'],
                                 ['E2'] + [eid_of(names, name) for name in names if name != 'prior']
                                 + [eid_of(names, 'prior')])
                self.assertEqual(row(result, p, text), [POLYP] + said)

    def test_d143_a_hard_wrapped_denial_beside_the_prior_segment_denial_shows_both(self):
        # Input B: S2w over two lines beside the prior-segment denial, in either order. 46e461e7f's row showed S2w's two
        # lines and never the prior-segment sentence; the installed release's conflict row shows S2w and PRIOR
        for first in ('withdrawal', 'prior'):
            with self.subTest(first=first):
                if first == 'withdrawal':
                    inv, text = colonoscopy(wrapped_withdrawal('E3', 'P3', 'P4'), prior('E5', 'P5'),
                                            lines={'P3': W_LINES[0], 'P4': W_LINES[1], 'P5': PRIOR})
                    s2w, other = 'E3', 'E5'
                else:
                    inv, text = colonoscopy(prior('E3', 'P3'), wrapped_withdrawal('E4', 'P4', 'P5'),
                                            lines={'P3': PRIOR, 'P4': W_LINES[0], 'P5': W_LINES[1]})
                    s2w, other = 'E4', 'E3'
                result = run(inv, text, [('45385', POLYP)])
                p = proposal(result, '45385')
                self.assert_asks(p, [' '.join(W_LINES), PRIOR])
                self.assertEqual(p.support['question_events'], ['E2', s2w, other])
                # the row keeps the wrapped statement's two lines together, then the other sentence
                self.assertEqual(row(result, p, text), [POLYP, W_LINES[0], W_LINES[1], PRIOR])
                self.assertEqual(named(p), [(W_LINES[0], s2w), (W_LINES[1], s2w), (POLYP, None), (PRIOR, other)])

    def test_d143_one_passage_of_every_statement_before_a_second_of_any(self):
        # three statements, the first over two lines: with the act's passage, MAX_PASSAGES (4) leaves room for one
        # passage of each - every statement is shown by its first line, and the wrapped one's second line is left out
        inv, text = colonoscopy(wrapped_withdrawal('E3', 'P3', 'P4'), framed('E5', 'P5'), prior('E6', 'P6'),
                                lines={'P3': W_LINES[0], 'P4': W_LINES[1], 'P5': FRAMED, 'P6': PRIOR})
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assert_asks(p, [' '.join(W_LINES), FRAMED, PRIOR])
        self.assertEqual(row(result, p, text), [POLYP, W_LINES[0], FRAMED, PRIOR])

    def test_d143_each_statement_is_shown_by_the_place_holding_its_status_words(self):
        # FRESH-1 C2MEM-031 r3 E23's shape: Gemini lists a heading line first among a denial's status passages, its
        # status words on a later line. The row shows the denial by the line the question quotes - the place holding
        # its status words, its source passage marked as the lead - never by the heading (this repair's first build
        # showed 'Splenic flexure: unresected lesion and localization tattoo' for E23); the source keeps its order
        heading = 'Prior segment: inspection only.'
        denial = prior('E5', 'P6')
        denial['status']['passages'] = ['P5', 'P6']
        inv, text = colonoscopy(framed('E3', 'P3'), BUILD['device'][0]('E4', 'P4'), denial,
                                lines={'P3': FRAMED, 'P4': DEVICE, 'P5': heading, 'P6': PRIOR})
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assert_asks(p, [FRAMED, DEVICE, PRIOR])
        self.assertEqual(row(result, p, text), [POLYP, FRAMED, DEVICE, PRIOR])
        self.assertEqual([(span['text'], span.get(questions.LEAD)) for span in p.support['source']
                          if span.get(questions.STATEMENT) == 'E5'], [(heading, None), (PRIOR, True)])

    def test_d143_a_question_about_one_statement_names_none_and_shows_as_before(self):
        # one contradiction: its source names no statement, and its row is the act's passage and the statement's, as
        # at 46e461e7f - on one line, and hard-wrapped over two
        inv, text = snare_beside('prior')
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(named(p), [(PRIOR, None), (POLYP, None)])
        self.assertEqual(row(result, p, text), [POLYP, PRIOR])
        inv, text = colonoscopy(wrapped_withdrawal('E3', 'P3', 'P4'), lines={'P3': W_LINES[0], 'P4': W_LINES[1]})
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(named(p), [(W_LINES[0], None), (W_LINES[1], None), (POLYP, None)])
        self.assertEqual(row(result, p, text), [POLYP, W_LINES[0], W_LINES[1]])

    def test_d143_every_statement_before_the_acts_own_passage(self):
        # a code citing another passage than the act's (here the colonoscope's line): the row shows that passage and
        # one passage of each statement before the act's own passage, in the source's order - with three statements
        # the act's passage is left out (MAX_PASSAGES), with two it is shown between them as the source lists it
        inv, text = snare_beside('framed', 'device', 'prior')
        result = run(inv, text, [('45385', COLONOSCOPE)])
        p = proposal(result, '45385')
        self.assert_asks(p, [FRAMED, DEVICE, PRIOR])
        self.assertEqual(row(result, p, text), [COLONOSCOPE, FRAMED, DEVICE, PRIOR])
        inv, text = snare_beside('framed', 'prior')
        result = run(inv, text, [('45385', COLONOSCOPE)])
        p = proposal(result, '45385')
        self.assertEqual(row(result, p, text), [COLONOSCOPE, FRAMED, POLYP, PRIOR])
        # the act is shown by its lead - the place holding its status words - never by a heading Gemini lists first
        # among its kind's passages
        heading = 'Sigmoid colon: polypectomy.'
        polyp = removed()
        polyp['kind'] = a('snare', 'removed', ['P8', 'P2'])
        inv, text = colonoscopy(framed('E3', 'P3'), prior('E4', 'P4'), lines={'P3': FRAMED, 'P4': PRIOR, 'P8': heading},
                                polyp=polyp)
        result = run(inv, text, [('45385', COLONOSCOPE)])
        p = proposal(result, '45385')
        self.assertEqual([span['text'] for span in p.support['source']], [FRAMED, heading, POLYP, PRIOR])
        self.assertEqual(row(result, p, text), [COLONOSCOPE, FRAMED, POLYP, PRIOR])

    def test_d143_another_question_of_the_code_reads_its_source_as_before(self):
        # the code's other questions share its source: their rows read it as before (at most PER_SOURCE of it) - with
        # no reach the snare beside three denials also asks the extent, whose row is the code's passage and the first
        # two of the source's, as at 46e461e7f
        inv, text = colonoscopy(*(maker(f'E{3 + index}', f'P{3 + index}') for index, maker in
                                  enumerate((framed, BUILD['device'][0], prior))),
                                lines={'P3': FRAMED, 'P4': DEVICE, 'P5': PRIOR}, reach=False)
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(asked(p), ['statement_scope', 'extent'])
        assessment = SimpleNamespace(revision=SimpleNamespace(text=text, pages=[]), services=result.services)
        extent = [item['text'] for item in answers._passages_of(assessment, [('extent', p.family, '45385')],
                                                                {'45385': [p]})]
        self.assertEqual(extent, [POLYP, FRAMED, DEVICE])
        self.assertEqual(row(result, p, text), [POLYP, FRAMED, DEVICE, PRIOR])

    def test_d143_a_source_that_names_no_statement_is_read_as_before(self):
        # questions.passages: the installed release's support never names a statement, and three of CPT Studio's own
        # passages beside the code's cited one still show two of them (PER_SOURCE); the same passages naming their
        # statements show all three in the statement_scope question's row (``named``), and two in any other row
        text = 'A polyp was removed. First statement here. Second statement here. Third statement here.'
        spans = [(text.index(part), text.index(part) + len(part), part)
                 for part in ('A polyp was removed.', 'First statement here.', 'Second statement here.',
                              'Third statement here.')]
        cited = [{'context_index': 0, 'start': spans[0][0], 'end': spans[0][1], 'text': spans[0][2], 'exact': True}]
        plain = [{'start': s, 'end': e, 'text': t} for s, e, t in spans[1:]]
        for named_row in (False, True):
            with self.subTest(named=named_row):
                self.assertEqual(questions.passages(cited, {'source': plain}, text, named=named_row), tuple(spans[:3]))
                self.assertEqual(questions.passages(cited, {'source': [dict(item, page=1) for item in plain]}, text,
                                                    named=named_row), tuple(spans[:3]))
        names = [dict(item, **{questions.STATEMENT: f'E{index}'}) for index, item in enumerate(plain, start=3)]
        self.assertEqual(questions.passages(cited, {'source': names}, text, named=True), tuple(spans))
        self.assertEqual(questions.passages(cited, {'source': names}, text), tuple(spans[:3]))
        self.assertEqual(questions.question_passages({}, 'gi.colonoscopy', 'statement_scope', cited, {'source': names},
                                                     text), tuple(spans))
        self.assertEqual(questions.question_passages({}, 'gi.colonoscopy', 'extent', cited, {'source': names}, text),
                         tuple(spans[:3]))
        # an empty or non-string name is no name
        for value in ('', None, 3):
            with self.subTest(name=value):
                unnamed = [dict(item, **{questions.STATEMENT: value}) for item in plain]
                self.assertEqual(questions.passages(cited, {'source': unnamed}, text, named=True), tuple(spans[:3]))


# --- D143 (2): a technique denial whose two devices are verified asks the contradiction -----------------------------

class D143TechniqueContradiction(Asks):
    """questions2 problem 1: on D126 (4)'s own input 46e461e7f asked technique, d353e64df statement_scope, and the
    installed release asks conflict:snare."""

    def snare_only(self, *more, lines=None):
        polyp = removed(technique=a('snare', 'snare', ['P2']), status_words='was removed with a snare')
        return colonoscopy(*more, lines={'P2': SNARE_ONLY, **(lines or {})}, polyp=polyp)

    def test_d143_a_technique_denial_whose_two_devices_are_verified_asks_whether_it_applies(self):
        inv, text = self.snare_only(no_cold(), lines={'P3': NO_COLD})
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'technique', 'technique_unresolved')])
        reading = events.Reading.of(inv)
        self.assertTrue(events.usable(reading.events['E2'], 'technique'))
        self.assertTrue(events.usable(reading.events['E3'], 'technique'))
        result = run(inv, text, [('45385', SNARE_ONLY)])
        p = proposal(result, '45385')
        self.assert_asks(p, [NO_COLD], act=WIDER, words='(“was removed with a snare”)?')
        self.assertEqual(p.support['question_events'], ['E2', 'E3'])
        self.assertEqual(row(result, p, text), [SNARE_ONLY, NO_COLD])

    def test_d143_beside_the_prior_segment_denial_both_are_asked(self):
        # the technique denial is a contradiction again: asked first (the act's own lesion: same-site), then the target
        # denial; 46e461e7f asked the prior-segment denial alone
        inv, text = self.snare_only(no_cold(), prior('E4', 'P4'), lines={'P3': NO_COLD, 'P4': PRIOR})
        self.assertEqual([item[2] for item in relations_of(inv)], ['technique', 'target'])
        result = run(inv, text, [('45385', SNARE_ONLY)])
        p = proposal(result, '45385')
        self.assert_asks(p, [NO_COLD, PRIOR], act=WIDER, words='(“was removed with a snare”)?')
        self.assertEqual(p.support['question_events'], ['E2', 'E3', 'E4'])
        self.assertEqual(row(result, p, text), [SNARE_ONLY, NO_COLD, PRIOR])

    def test_d143_two_other_devices_ask_the_contradiction(self):
        # questions2 problem 3's shape (recorded there): both devices verified as 'other' - UNKNOWN to the pairing
        # table - asked technique at 46e461e7f; the contradiction, as at d353e64df
        act_line = 'A 6 mm sessile polyp in the sigmoid colon was removed with a loop device.'
        denial_line = 'No loop device was used for the 6 mm sessile polyp.'
        polyp = removed(technique=a('other', 'loop device', ['P2']), status_words='was removed with a loop device')
        denial = act('E3', 'P3', 'snare', 'loop device', status='not_performed', status_words='No loop device was used',
                     technique=a('other', 'loop device', ['P3']),
                     scope=sc('single_target', 'the 6 mm sessile polyp', ['P3'], targets=['L1']),
                     target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P3']))
        inv, text = colonoscopy(denial, lines={'P2': act_line, 'P3': denial_line}, polyp=polyp)
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'technique', 'technique_unresolved')])
        p = proposal(run(inv, text, [('45385', act_line)]), '45385')
        self.assert_asks(p, [denial_line], act=WIDER, words='(“was removed with a loop device”)?')

    def test_d143_control_the_acts_own_device_unverified_keeps_the_technique_question(self):
        # D91, unchanged: the unknown side is the act's own device ('snare' given in words the act's line does not
        # hold), so the relation asks which technique was used
        polyp = removed(technique=a('snare', 'loop', ['P2']), status_words='was removed with a snare')
        inv, text = colonoscopy(no_cold(), lines={'P2': SNARE_ONLY, 'P3': NO_COLD}, polyp=polyp)
        reading = events.Reading.of(inv)
        self.assertFalse(events.usable(reading.events['E2'], 'technique'))
        self.assertEqual([item[2] for item in relations_of(inv)], ['technique'])
        p = proposal(run(inv, text, [('45385', SNARE_ONLY)]), '45385')
        self.assertEqual(asked(p), ['technique'])


# --- D143 (3): a scope whose words do not locate is quoted by its own passages --------------------------------------

UNLOCATED = {'P1': COLONOSCOPE, 'P2': 'Biopsies were taken from the ileocolonic anastomosis with cold forceps.',
             'P3': 'Random biopsies were collected for dysplasia surveillance; they were not taken from any',
             'P4': 'polyp or lesion described below.'}
BIOPSY_ACT = 'forceps biopsy (cold forceps) at the anastomosis'


def biopsy() -> dict:
    return act('E2', 'P2', 'biopsy', 'Biopsies', status_words='were taken',
               technique=a('cold_forceps', 'cold forceps', ['P2']),
               target=tg('', 'anastomosis', 'ileocolonic anastomosis', ['P2']))


def unlocated_denial(words: str = 'any resected polyp or suspicious lesion', passages=('P3', 'P4')) -> dict:
    """FRESH-1 C2MEM-031 r3's E17's shape: its target absent, its scope listed_targets, the scope's words (Gemini's) in
    none of its scope's passages - this line and the next (the recorded E17: P50 and P51, one character apart)."""
    return act('E3', 'P3', 'biopsy', 'biopsies', status='not_performed', status_words='were not taken',
               scope=sc('listed_targets', words, list(passages)))


class D143UnlocatedScope(SimpleTestCase):
    """questions2 problem 2: D126 (1) read only LOCATED words, so the recorded E17 kept the status words' one line."""

    def scope_reading(self, lines=None, denial=None):
        inv, text = inventory({**UNLOCATED, **(lines or {})}, events=[exam(), biopsy(), denial or unlocated_denial()],
                              reach=[reached()])
        return inv, text, events.Reading.of(inv)

    def test_d143_the_service_question_quotes_the_scopes_own_passages_across_the_wrap(self):
        inv, _, reading = self.scope_reading()
        scope = reading.events['E3']['scope']
        self.assertEqual((scope['state'], scope['words'], scope['passages']), ('unverified', None, ['P3', 'P4']))
        self.assertIn('words_unlocated', scope['reasons'])
        self.assertEqual(relations_of(inv), [('E3', 'E2', 'scope', 'scope_unresolved')])
        question = events.focus_question(reading, reading.events['E2'])
        said = f'“{UNLOCATED["P3"]} {UNLOCATED["P4"]}”'
        self.assertEqual((question.fact, question.events), ('statement_scope', ('E2', 'E3')))
        self.assertEqual(question.question, f'Does {said} apply to the {BIOPSY_ACT} (“were taken”)?')
        self.assertEqual(question.reason, f'The document states {said}; CPT Studio could not confirm from the document '
                                          f'whether that statement applies to the {BIOPSY_ACT}.')

    def test_d143_the_codes_question_quotes_them_too(self):
        inv, text, _ = self.scope_reading()
        p = proposal(run(inv, text, [('45380', UNLOCATED['P2'])]), '45380')
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['statement_scope'], events.UNRESOLVED))
        self.assertEqual(p.clarifications[0].question,
                         f'Does “{UNLOCATED["P3"]} {UNLOCATED["P4"]}” apply to the {BIOPSY_ACT} (“were taken”)?')

    def test_d143_scope_passages_apart_are_joined_with_an_ellipsis(self):
        # the scope's passages a sentence apart: each whole, the gap marked
        lines = {'P4': 'The anastomosis was patent.', 'P5': 'polyp or lesion described below.'}
        inv, _, reading = self.scope_reading(lines, unlocated_denial(passages=('P3', 'P5')))
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual(question.question, f'Does “{UNLOCATED["P3"]} … {lines["P5"]}” apply to the {BIOPSY_ACT} '
                                            '(“were taken”)?')

    def test_d143_control_a_scope_with_no_words_keeps_the_status_line(self):
        # only words Gemini gave and the document does not hold are read through the passages: a scope with no words
        # (words_missing) adds nothing, as at 46e461e7f
        inv, _, reading = self.scope_reading(denial=unlocated_denial(words=''))
        reasons = reading.events['E3']['scope']['reasons']
        self.assertIn('words_missing', reasons)
        self.assertNotIn('words_unlocated', reasons)
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual(question.question, f'Does “{UNLOCATED["P3"]}” apply to the {BIOPSY_ACT} (“were taken”)?')

    def test_d143_control_located_scope_words_read_as_before(self):
        # D126 (1), unchanged: the scope's words located on the next line join the sentence across the wrap
        located = act('E3', 'P3', 'biopsy', 'biopsies', status='not_performed', status_words='were not taken',
                      scope=sc('single_target', 'polyp or lesion described below', ['P4']))
        inv, _, reading = self.scope_reading(denial=located)
        question = events.focus_question(reading, reading.events['E2'])
        self.assertEqual(question.question, f'Does “{UNLOCATED["P3"]} {UNLOCATED["P4"]}” apply to the {BIOPSY_ACT} '
                                            '(“were taken”)?')


# --- D143 (4): a doubt on the act never displaces its denial -------------------------------------------------------

DOUBT_LINE = 'It is unclear whether the sigmoid polyp was removed completely.'
ANY_LINE = 'It is unclear whether any polyp was removed.'


def doubt_event(any_polyp: bool = False) -> dict:
    if any_polyp:
        return act('E4', 'P4', 'removal', 'removed', status='uncertain',
                   status_words='It is unclear whether any polyp was removed',
                   scope=sc('all_of_kind', 'any polyp', ['P4']))
    return act('E4', 'P4', 'removal', 'removed', status='uncertain',
               status_words='It is unclear whether the sigmoid polyp was removed',
               target=tg('L1', 'sigmoid_colon', 'the sigmoid polyp', ['P4']),
               scope=sc('single_target', 'the sigmoid polyp', ['P4']))


def doubt_document(*, doubt_first: bool = False, any_polyp: bool = False, dated: bool = False, denied: bool = True,
                   listed_first: bool = False):
    """(the normalized inventory, the text) of currency2 problem 0's input: the undated note's colonoscopy (E1), its
    snare 'On 11/09/2026, ...' (E2, a pending check), 'Impression: No polypectomy was performed.' (E3) and a doubt on
    the snare (E4, P4) - the doubt's line after the impression, or before it (``doubt_first``), or before the snare's
    own line with its event listed before the snare's (``listed_first``); with ``dated`` the document's own date line
    too (the dated twin)."""
    options = dict(date_lines={'P0': DATE_LINE}, date_of_service=STATED) if dated else {}
    value, lines = denial_answer(denied=denied, **options)
    line = ANY_LINE if any_polyp else DOUBT_LINE
    value['passages'].append({'id': 'P4', 'text': line})
    if listed_first:
        value['events'].insert(1, doubt_event(any_polyp))  # after the examination, before the snare
    else:
        value['events'].append(doubt_event(any_polyp))
    lines['P4'] = line
    if (doubt_first and denied) or listed_first:
        rest = [pid for pid in lines if pid not in ('P1', 'P2', 'P3', 'P4')]
        order = rest + (['P1', 'P4', 'P2', 'P3'] if listed_first else ['P1', 'P2', 'P4', 'P3'])
        order = [pid for pid in order if pid in lines]
        lines = {pid: lines[pid] for pid in order}
        value['passages'] = [next(item for item in value['passages'] if item['id'] == pid) for pid in order]
    text = '\n'.join(lines.values()) + '\n'
    return normalize.normalize(accepted(value), text), text


def member(day):
    return {'service_date': day} if day else {}


class D143DenialBesideADoubt(SimpleTestCase):
    """currency2 problem 0 (medium): D128 stores the denial's relation UNRESOLVED(time), and h2's doubt took the code's
    one question before h3 could ask the contradiction."""

    def assert_both_asked(self, result, text: str, doubt: str = DOUBT_LINE):
        p = proposal(result, '45385')
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['statement_scope'], events.UNRESOLVED))
        self.assertEqual(p.clarifications[0].question,
                         f'Does “{DENIAL}” or “{doubt}” apply to the {SNARE} {SNARE_WORDS}')
        self.assertEqual(p.clarifications[0].reason,
                         f'The document states “{DENIAL}” and “{doubt}”; CPT Studio could not confirm from the '
                         f'document whether those statements apply to the {SNARE}.')
        self.assertEqual(p.support['question_events'], ['E2', 'E3', 'E4'])
        self.assertEqual(row(result, p, text), [DATED_POLYP, DENIAL, doubt])

    def test_d143_with_the_members_equal_date_the_denial_is_asked_beside_the_doubt(self):
        # the review's input: 46e461e7f asked performed_status quoting the doubt alone; the installed release asks
        # conflict:snare (its conflicts check warns)
        for name, options, doubt in (('the doubt after the impression', {}, DOUBT_LINE),
                                     ('the doubt before it', {'doubt_first': True}, DOUBT_LINE),
                                     ("the doubt of 'any polyp'", {'any_polyp': True}, ANY_LINE)):
            with self.subTest(name):
                inv, text = doubt_document(**options)
                self.assertEqual(stored_relations(inv), [('unresolved', 'E3', 'E2', 'time', 'time_unresolved'),
                                                         ('doubt', 'E4', 'E2', 'status', 'in_doubt')])
                self.assert_both_asked(run(inv, text, [('45385', DATED_POLYP)], user_values=member('2026-11-09')),
                                       text, doubt)

    def test_d143_a_doubt_listed_before_the_snare_never_displaces_the_denial(self):
        # the doubting sentence stated and listed before the snare is itself a candidate (a removal of unstated method),
        # so h2 met its own uncertain status first and asked whether IT was done, quoting it alone (46e461e7f): the
        # snare it doubts has the denial's contradiction, so the one question asks both, about the snare
        inv, text = doubt_document(listed_first=True)
        self.assertEqual([item['id'] for item in inv.events['events']], ['E1', 'E4', 'E2', 'E3'])
        self.assertEqual(sorted(stored_relations(inv)), [('doubt', 'E4', 'E2', 'status', 'in_doubt'),
                                                         ('unresolved', 'E3', 'E2', 'time', 'time_unresolved')])
        self.assert_both_asked(run(inv, text, [('45385', DATED_POLYP)], user_values=member('2026-11-09')), text)
        # with no date the denial is no contradiction (the snare's own time unusable): the doubt asks about itself, as
        # at 46e461e7f
        p = proposal(run(inv, text, [('45385', DATED_POLYP)]), '45385')
        self.assertEqual((asked(p), p.support['question_events']), (['performed_status'], ['E4']))

    def test_d143_a_doubt_beside_the_prior_segment_denial_asks_both(self):
        # the rule is h2's against h3's, not D128's: on a dated document the snare's verified sigmoid colon beside the
        # prior-segment denial (UNRESOLVED(target)) and a doubt of the snare - 46e461e7f asked the doubt alone
        inv, text = colonoscopy(prior('E3', 'P3'), doubt_event(), lines={'P3': PRIOR, 'P4': DOUBT_LINE})
        self.assertEqual([item[0] for item in stored_relations(inv)], ['unresolved', 'doubt'])
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(asked(p), ['statement_scope'])
        self.assertEqual(p.clarifications[0].question, f'Does “{PRIOR}” or “{DOUBT_LINE}” apply to the {SNARE} '
                                                       f'{SNARE_WORDS}')
        self.assertEqual(p.support['question_events'], ['E2', 'E3', 'E4'])
        self.assertEqual(row(result, p, text), [POLYP, PRIOR, DOUBT_LINE])

    def test_d143_control_with_no_date_or_another_date_the_doubt_asks_as_before(self):
        # the snare's own time is then unusable, so the denial's relation is no contradiction (D91): the doubt's
        # performed_status, as at 46e461e7f and as the installed release asks
        inv, text = doubt_document()
        for day in (None, '2026-11-10'):
            with self.subTest(member=day):
                p = proposal(run(inv, text, [('45385', DATED_POLYP)], user_values=member(day)), '45385')
                self.assertEqual((asked(p), p.support['reason'], p.support['question_events']),
                                 (['performed_status'], events.DOUBT, ['E2', 'E4']))

    def test_d143_control_the_dated_document_asks_the_conflict(self):
        # the document's own date makes the denial a CONTRADICTION: h1 asks conflict:snare, as before
        inv, text = doubt_document(dated=True)
        self.assertEqual(stored_relations(inv)[0][:2], ('contradiction', 'E3'))
        result = run(inv, text, [('45385', DATED_POLYP)])
        self.assertEqual(asked(proposal(result, '45385')), ['conflict:snare'])
        self.assertEqual(conflicts_check(result).status, 'warn')

    def test_d143_control_a_doubt_with_no_denial_keeps_its_question(self):
        inv, text = doubt_document(denied=False)
        p = proposal(run(inv, text, [('45385', DATED_POLYP)], user_values=member('2026-11-09')), '45385')
        self.assertEqual((asked(p), p.support['reason'], p.support['question_events']),
                         (['performed_status'], events.DOUBT, ['E2', 'E4']))
