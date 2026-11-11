"""DECISIONS D150 (the Gemini migration's round-5d repair "questions4"; the review of round 5c's "questions3" patch,
problems 0 and 1): what a held code's statement_scope question asks beside a doubt, and what the member's details row
shows when the code cites more than one passage.

- (1) Problem 0 (high): D143's events._h3_beside_doubt read, when h2 met a DOUBT relation, only the act that relation
  doubts. A doubt of two removals ('It is unclear whether any polyp was removed.') therefore displaced the denial of the
  other one: with the doubting event listed after the removals, the code asked performed_status about the sigmoid
  removal and the rectal denial was asked and shown nowhere; listed first, it asked the rectal denial beside the doubt.
  The installed release asks conflict:snare in both orders. Both branches now read every positive act the doubting
  statement doubts, h2's own act first: both orders ask whether the rectal denial or the doubt applies to the rectal
  snare.
- (2) Problem 1 (medium): D143's questions._statements_kept kept the code's cited passages (at most PER_SOURCE, 2)
  before any statement, so a code citing two passages left room for two statements only (MAX_PASSAGES, 4): finding 3's
  framed and device denials beside the prior-segment denial, 45385 citing the snare's line and the colonoscope's,
  showed the first two statements and never the prior-segment denial. The code's first passage now comes before one
  passage of each statement, its other passages after them.

Only questions, their passages and the member's row change, and on (1)'s inputs support['reason'] (doubt to
unresolved) and the detail of the events.match and events.relation checks: status, bucket, every check's status, READY
and the exclusion are untouched.
SYNTHETIC: the shared S08 builders (tests.test_interpretation_events, tests.test_interpretation_identity) and the
round-4 and round-5 builders over fictional documents, in the shapes of the review's inputs (RC, RA and Input A with two
cited passages: constructed by the reviewer, not attested). Nothing is sent."""
from __future__ import annotations

import itertools

from django.test import SimpleTestCase

from studio.interpretation import events, normalize
from studio.validation import questions
from tests.test_interpretation_events import (COLONOSCOPE, L1, POLYP, asked, check, colonoscopy, exam, inventory,
                                              proposal, reached, removed, run)
from tests.test_interpretation_identity import a, accepted, act, les, sc, snare, tg
from tests.test_interpretation_r3_currency import NOT_STATED
from tests.test_interpretation_r4_currency_pairing import stored_relations
from tests.test_interpretation_r4_questions import PRIOR, SNARE_WORDS, prior
from tests.test_interpretation_r5_questions import BUILD, Asks, eid_of, snare_beside
from tests.test_interpretation_r5c_questions import row

ANY_LINE = 'It is unclear whether any polyp was removed.'
SIGMOID = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
DATED_RECTAL = 'On 11/09/2026, a 4 mm sessile polyp in the rectum was removed with a cold snare.'
RECTAL = 'A 4 mm sessile polyp in the rectum was removed with a cold snare.'
RECTAL_DENIAL = 'No polypectomy of the rectal polyp was performed.'
RECTAL_DEVICE = 'Neither the EMR electrosurgical snare nor cautery was used to treat the rectal polyp.'
RECTAL_SNARE = 'snare removal (cold snare) of the 4 mm sessile polyp in the rectum'
L2 = les('L2', '4 mm sessile polyp', 'P3', landmark='rectum', site_words='rectum', size_words='4 mm')


def any_doubt(eid: str = 'E5', pid: str = 'P5') -> dict:
    """The all_of_kind doubt of every removal (D143's ANY_LINE)."""
    return act(eid, pid, 'removal', 'removed', status='uncertain',
               status_words='It is unclear whether any polyp was removed', scope=sc('all_of_kind', 'any polyp', [pid]))


def rectal_snare(eid: str = 'E3', pid: str = 'P3', **changes) -> dict:
    return snare(eid, pid, target=tg('L2', 'rectum', '4 mm sessile polyp in the rectum', [pid]), **changes)


def undated_two(*, doubt_first: bool = False) -> tuple:
    """(inventory, text) of the review's Input RC: an undated note - the colonoscope (E1, P1), the sigmoid removal
    (E2, P2, its time current_encounter with no words), the rectal removal 'On 11/09/2026, ...' (E3, P3, a pending
    check), the rectal denial (E4, P4) and the doubt of any polyp (E5, P5) - the doubt's event listed after the
    removals, or first (``doubt_first``); its line last either way."""
    lines = {'P1': COLONOSCOPE, 'P2': SIGMOID, 'P3': DATED_RECTAL, 'P4': RECTAL_DENIAL, 'P5': ANY_LINE}
    sigmoid = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P2']))
    rectal = rectal_snare(time=a('current_encounter', 'On 11/09/2026', ['P3']))
    denial = act('E4', 'P4', 'removal', 'polypectomy', status='not_performed', status_words='No polypectomy',
                 scope=sc('single_target', 'the rectal polyp', ['P4'], targets=['L2']),
                 target=tg('L2', 'rectum', 'the rectal polyp', ['P4']))
    found = [exam(), sigmoid, rectal, denial]
    if doubt_first:
        found.insert(1, any_doubt())
    else:
        found.append(any_doubt())
    lesions = [les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                   size_words='6 mm'),
               les('L2', '4 mm sessile polyp', 'P3', landmark='rectum', site_words='rectum', size_words='4 mm')]
    value = {'passages': [{'id': pid, 'text': text} for pid, text in lines.items()],
             'encounter': {'date_of_service': NOT_STATED, 'documenting_endoscopist': {'words': '', 'passages': []},
                           'team': [], 'anatomy': [], 'reach': [reached()], 'visit_facts': []},
             'lesions': lesions, 'events': found, 'open_questions': []}
    text = '\n'.join(lines.values()) + '\n'
    return normalize.normalize(accepted(value), text), text


def rectal_device(eid: str = 'E4', pid: str = 'P4') -> dict:
    """D102's device denial (finding 3's S4 shape: 'cautery', device_missing) of the RECTAL polyp only."""
    return act(eid, pid, 'snare', 'EMR electrosurgical snare', status='not_performed',
               status_words='Neither the EMR electrosurgical snare nor cautery was used',
               technique=a('hot_snare', 'cautery', [pid]),
               scope=sc('single_target', 'the rectal polyp', [pid]),
               target=tg('L2', 'rectum', 'the rectal polyp', [pid]))


def dated_two(*, doubt_first: bool = False) -> tuple:
    """(inventory, text) of the review's Input RA: the dated colonoscopy, the sigmoid snare (E2), the rectal snare (E3),
    the rectal device denial (E4) and the doubt of any polyp (E5) - its event listed after the removals, or first."""
    lines = {'P3': RECTAL, 'P4': RECTAL_DEVICE, 'P5': ANY_LINE}
    if doubt_first:
        return inventory({'P1': COLONOSCOPE, 'P2': POLYP, **lines},
                         events=[exam(), any_doubt(), removed(), rectal_snare(), rectal_device()], lesions=[L1, L2],
                         reach=[reached()])
    return colonoscopy(rectal_snare(), rectal_device(), any_doubt(), lines=lines, lesions=(L1, L2))


# --- D150 (1): a doubt of two removals never displaces the denial of the act it doubts -------------------------------

class D150DoubtOfTwoRemovals(SimpleTestCase):
    """Problem 0 (high): the relation branch of events._h3_beside_doubt read only the act h2 met."""

    def assert_rectal_asked(self, result, denial: str, row_act: str, text: str, cited_row=None):
        p = proposal(result, '45385')
        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                         ('selected', 'needs_clarification', ['statement_scope'], events.UNRESOLVED))
        self.assertEqual(p.clarifications[0].question,
                         f'Does “{denial}” or “{ANY_LINE}” apply to the {RECTAL_SNARE} {SNARE_WORDS}')
        self.assertEqual(p.clarifications[0].reason,
                         f'The document states “{denial}” and “{ANY_LINE}”; CPT Studio could not confirm from the '
                         f'document whether those statements apply to the {RECTAL_SNARE}.')
        self.assertEqual(p.support['question_events'], ['E3', 'E4', 'E5'])
        self.assertEqual(check(p, 'events.relation').status, 'warn')
        self.assertEqual(row(result, p, text), cited_row or [row_act, denial, ANY_LINE])

    def test_d150_a_doubt_of_two_removals_asks_the_rectal_denial_in_either_order(self):
        # Input RC with the member's date 2026-11-09 (the rectal removal's own day): D128 leaves the denial's relation
        # UNRESOLVED(time), the doubt doubts both removals. e5628be56: the doubt listed after the removals asked
        # performed_status about the sigmoid removal (question_events [E2, E5]) and the rectal denial was asked and
        # shown nowhere; listed first, the denial beside the doubt. The installed release: conflict:snare in both
        for doubt_first in (False, True):
            with self.subTest(doubt_first=doubt_first):
                inv, text = undated_two(doubt_first=doubt_first)
                self.assertEqual(sorted(stored_relations(inv)),
                                 [('doubt', 'E5', 'E2', 'status', 'in_doubt'),
                                  ('doubt', 'E5', 'E3', 'status', 'in_doubt'),
                                  ('independent', 'E4', 'E2', 'target', 'another_lesion'),
                                  ('unresolved', 'E4', 'E3', 'time', 'time_unresolved')])
                result = run(inv, text, [('45385', DATED_RECTAL)], user_values={'service_date': '2026-11-09'})
                self.assert_rectal_asked(result, RECTAL_DENIAL, DATED_RECTAL, text)

    def test_d150_the_device_denial_beside_a_doubt_of_two_removals_in_either_order(self):
        # Input RA (dated): D102's device denial of the rectal polyp, UNRESOLVED(technique) beside the rectal snare's
        # verified cold snare; the same doubt. e5628be56: listed after, performed_status about the sigmoid removal
        for doubt_first in (False, True):
            for cite, shown in ((RECTAL, None), (POLYP, [POLYP, RECTAL_DEVICE, RECTAL, ANY_LINE])):
                with self.subTest(doubt_first=doubt_first, cite=cite):
                    inv, text = dated_two(doubt_first=doubt_first)
                    self.assertIn(('unresolved', 'E4', 'E3', 'technique', 'technique_unresolved'),
                                  stored_relations(inv))
                    result = run(inv, text, [('45385', cite)])
                    self.assert_rectal_asked(result, RECTAL_DEVICE, RECTAL, text, shown)

    def test_d150_control_with_no_date_the_doubt_asks_as_before(self):
        # no member's date: the rectal snare's own time is unusable, so the denial's relation is no contradiction (D91)
        # and h2's question stands, as at e5628be56 - about the sigmoid removal (listed after) or the doubt itself
        # (listed first); the installed release asks performed_status too
        for doubt_first, events_asked in ((False, ['E2', 'E5']), (True, ['E5'])):
            with self.subTest(doubt_first=doubt_first):
                inv, text = undated_two(doubt_first=doubt_first)
                p = proposal(run(inv, text, [('45385', DATED_RECTAL)]), '45385')
                self.assertEqual((asked(p), p.support['reason'], p.support['question_events']),
                                 (['performed_status'], events.DOUBT, events_asked))

    def test_d150_control_a_doubt_that_doubts_no_act_keeps_its_question(self):
        # D143's recorded residual 3, unchanged: a doubt of ANOTHER lesion, INDEPENDENT of the snare, doubts no act
        # with a denial - h2's question about it stands and the prior-segment denial is not asked (one question per
        # code); the installed release asks conflict:snare there
        rectal_doubt = 'It is unclear whether the 4 mm rectal polyp was removed.'
        doubt = act('E4', 'P4', 'removal', 'removed', status='uncertain',
                    status_words='It is unclear whether the 4 mm rectal polyp was removed',
                    target=tg('L2', 'rectum', 'the 4 mm rectal polyp', ['P4']),
                    scope=sc('single_target', 'the 4 mm rectal polyp', ['P4']))
        lesion = les('L2', '4 mm sessile polyp', 'P4', landmark='rectum', site_words='rectum', size_words='4 mm')
        inv, text = colonoscopy(prior('E3', 'P3'), doubt, lines={'P3': PRIOR, 'P4': rectal_doubt}, lesions=(L1, lesion))
        self.assertNotIn('doubt', [item[0] for item in stored_relations(inv)])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual((asked(p), p.support['reason'], p.support['question_events']),
                         (['performed_status'], events.DOUBT, ['E4']))


# --- D150 (2): every statement in the member's row, whatever number of passages the code cites ----------------------

class D150StatementsBesideTwoCitedPassages(Asks):
    """Problem 1 (medium): questions._statements_kept kept the code's two cited passages before any statement."""

    def test_d150_three_denials_beside_two_cited_passages_in_every_order(self):
        # Input A, 45385 citing the snare's line and the colonoscope's: e5628be56's row was [the snare, the colonoscope,
        # the first two statements] in every order, never the third; the installed release's conflict row shows the
        # snare and all three statements
        for names in itertools.permutations(('framed', 'device', 'prior')):
            with self.subTest(order=names):
                inv, text = snare_beside(*names)
                result = run(inv, text, [('45385', (POLYP, COLONOSCOPE))])
                p = proposal(result, '45385')
                said = [BUILD[name][1] for name in names if name != 'prior'] + [PRIOR]  # same-site first, then target
                self.assert_asks(p, said)
                self.assertEqual(p.support['question_events'],
                                 ['E2'] + [eid_of(names, name) for name in names if name != 'prior']
                                 + [eid_of(names, 'prior')])
                self.assertEqual(row(result, p, text), [POLYP] + said)

    def test_d150_the_codes_first_passage_is_the_one_kept(self):
        # the code citing the colonoscope's line first: that line is kept, then the three statements - the act's own
        # passage is left out of the row, as with a code citing the colonoscope alone (D143's recorded residual 2)
        inv, text = snare_beside('framed', 'device', 'prior')
        result = run(inv, text, [('45385', (COLONOSCOPE, POLYP))])
        p = proposal(result, '45385')
        self.assertEqual(row(result, p, text), [COLONOSCOPE, BUILD['framed'][1], BUILD['device'][1], PRIOR])

    def test_d150_control_two_statements_beside_two_cited_passages_show_as_before(self):
        # with room for every statement, the row is e5628be56's: the code's two passages, then the statements
        for cite, head in (((POLYP, COLONOSCOPE), [POLYP, COLONOSCOPE]), ((COLONOSCOPE, POLYP), [COLONOSCOPE, POLYP])):
            with self.subTest(cite=cite):
                inv, text = snare_beside('framed', 'prior')
                result = run(inv, text, [('45385', cite)])
                p = proposal(result, '45385')
                self.assertEqual(row(result, p, text), head + [BUILD['framed'][1], PRIOR])

    def test_d150_control_one_cited_passage_shows_as_before(self):
        inv, text = snare_beside('prior', 'framed', 'device')
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(row(result, p, text), [POLYP, BUILD['framed'][1], BUILD['device'][1], PRIOR])


TEXT = ('A polyp was removed. The scope reached the cecum. First statement here. Second statement here. '
        'Third statement here. Fourth statement here.')


def spans(*parts) -> list:
    return [(TEXT.index(part), TEXT.index(part) + len(part), part) for part in parts]


def cited_of(*parts) -> list:
    return [{'context_index': 0, 'start': s, 'end': e, 'text': t, 'exact': True} for s, e, t in spans(*parts)]


def named_source(*parts) -> list:
    return [{'start': s, 'end': e, 'text': t, questions.STATEMENT: f'E{index}'}
            for index, (s, e, t) in enumerate(spans(*parts), start=3)]


ACT, SCOPE = 'A polyp was removed.', 'The scope reached the cecum.'
FIRST, SECOND, THIRD, FOURTH = ('First statement here.', 'Second statement here.', 'Third statement here.',
                                'Fourth statement here.')


class D150StatementsKept(SimpleTestCase):
    """questions.passages(named=True), the statement_scope row's reading, on constructed sources."""

    def test_d150_each_statement_keeps_its_first_passage_beside_the_codes(self):
        cited = cited_of(ACT, SCOPE)
        support = {'source': named_source(FIRST, SECOND, THIRD)}
        self.assertEqual(questions.passages(cited, support, TEXT, named=True), tuple(spans(ACT, FIRST, SECOND, THIRD)))
        self.assertEqual(questions.question_passages({}, 'gi.colonoscopy', 'statement_scope', cited, support, TEXT),
                         tuple(spans(ACT, FIRST, SECOND, THIRD)))
        # two statements: room for the code's second passage, shown with the code's, as before
        two = {'source': named_source(FIRST, SECOND)}
        self.assertEqual(questions.passages(cited, two, TEXT, named=True), tuple(spans(ACT, SCOPE, FIRST, SECOND)))
        # four: MAX_PASSAGES beside the code's first passage leaves room for three
        four = {'source': named_source(FIRST, SECOND, THIRD, FOURTH)}
        self.assertEqual(questions.passages(cited, four, TEXT, named=True), tuple(spans(ACT, FIRST, SECOND, THIRD)))

    def test_d150_a_passage_that_is_one_of_the_codes_is_shown_in_the_codes_place(self):
        # the code citing a statement's own line as its second passage: shown once, where the code's passages are
        # shown, as at e5628be56 - never moved among the statements
        cited = cited_of(ACT, SECOND)
        support = {'source': named_source(FIRST, SECOND)}
        self.assertEqual(questions.passages(cited, support, TEXT, named=True), tuple(spans(ACT, SECOND, FIRST)))

    def test_d150_control_another_fact_and_an_unnamed_source_read_as_before(self):
        cited = cited_of(ACT, SCOPE)
        named = {'source': named_source(FIRST, SECOND, THIRD)}
        plain = {'source': [{key: item[key] for key in ('start', 'end', 'text')} for item in named['source']]}
        legacy = tuple(spans(ACT, SCOPE, FIRST, SECOND))
        self.assertEqual(questions.passages(cited, named, TEXT), legacy)
        self.assertEqual(questions.passages(cited, plain, TEXT, named=True), legacy)
        self.assertEqual(questions.question_passages({}, 'gi.colonoscopy', 'extent', cited, named, TEXT), legacy)
