"""Lesion distinctness and act-to-lesion identity (Gemini migration slice S03; design/contract.md 6.1-6.3, as
design/ADJUDICATION.md C-11, C-15 and EB1 amend them), TEXT-ONLY: every distinctness literal of 6.3 with C-11's size
tolerance and its "a shared literal says same" rule and C-15's colon regions; every identity rule of 6.2, passing and
failing (the statement tie, the lexical tie, literal consistency, discrimination, the lesion verified), an open identity
question, and the reasons counted in the verification report. Synthetic answers built in code, read by read.read and
normalized; nothing is sent.

The answer builders here (a, tg, sc, act, les, answer, normalized, built, ev, lesion, relations_of) are the S03 test
modules' shared builders: test_interpretation_relations and test_interpretation_slips import them."""
from __future__ import annotations

import json
import sys
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation import identity, normalize, read, verify

DATE_LINE = 'Date of service: 11/09/2026.'


# --- the shared builders -----------------------------------------------------------------------------------------------

def a(value: str, words: str = '', passages=()) -> dict:
    """An attribute as Gemini gives it."""
    return {'value': value, 'words': words, 'passages': list(passages)}


def tg(lesion: str = '', landmark: str = 'not_stated', words: str = '', passages=()) -> dict:
    return {'lesion': lesion, 'landmark': landmark, 'words': words, 'passages': list(passages)}


def sc(value: str = 'not_applicable', words: str = '', passages=(), targets=()) -> dict:
    return {'value': value, 'targets': list(targets), 'words': words, 'passages': list(passages)}


def act(eid: str, passage: str, kind: str, kind_words: str, *, status: str = 'performed', status_words: str = '',
        **changes) -> dict:
    """An event of ``kind`` stated in ``passage``: a colonoscopy act of this encounter by the documenting team (the frame
    defaults), no device, no target, no scope, unless ``changes`` say otherwise."""
    item = {'id': eid, 'procedure': a('colonoscopy'), 'kind': a(kind, kind_words, [passage]),
            'technique': a('not_stated'), 'target': tg(), 'time': a('current_encounter'),
            'performer': a('documenting_team'), 'status': a(status, status_words or kind_words, [passage]),
            'scope': sc(), 'purpose': a('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []}
    item.update(changes)
    return item


def les(lid: str, words: str, passage: str, *, landmark: str = 'not_stated', site_words: str = '',
        size_words: str = '', multiplicity: str = 'single') -> dict:
    return {'id': lid, 'words': words, 'landmark': landmark, 'site_words': site_words, 'size_words': size_words,
            'multiplicity': multiplicity, 'passages': [passage]}


def answer(lines: dict, *, events=(), lesions=(), open_questions=(), **encounter) -> tuple:
    """A schema-valid answer over a synthetic document whose lines are DATE_LINE (P0) then ``lines`` ({id: text}), and
    the document's text."""
    passages = {'P0': DATE_LINE, **lines}
    facts = {'date_of_service': {'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026', 'passages': ['P0'],
                                 'other_dates': []},
             'documenting_endoscopist': {'words': '', 'passages': []}, 'team': [], 'anatomy': [], 'reach': [],
             'visit_facts': []}
    facts.update(encounter)
    value = {'passages': [{'id': pid, 'text': text} for pid, text in passages.items()], 'encounter': facts,
             'lesions': list(lesions), 'events': list(events), 'open_questions': list(open_questions)}
    return value, '\n'.join(passages.values()) + '\n'


def accepted(value: dict) -> dict:
    parsed = read.read(json.dumps(value))
    assert not isinstance(parsed, read.Refusal), parsed
    return parsed


def normalized(lines: dict, **options) -> normalize.Inventory:
    """The inventory of the answer, normalized with the real linked steps (slice S03's)."""
    value, text = answer(lines, **options)
    return normalize.normalize(accepted(value), text)


def built(lines: dict, steps=(), **options) -> normalize.Draft:
    """The Draft of the answer after normalize's own steps, then ``steps`` called on it in order."""
    value, text = answer(lines, **options)
    with mock.patch.object(normalize, 'LINKED_STEPS', ()):
        draft = normalize.Draft(accepted(value), text)
        draft.build()
    for step in steps:
        step(draft)
    return draft


def ev(inventory, eid: str) -> dict:
    events = inventory.events['events'] if isinstance(inventory, normalize.Inventory) else inventory.events.values()
    return next(item for item in events if item['id'] == eid)


def lesion(inventory, lid: str) -> dict:
    lesions = inventory.events['lesions'] if isinstance(inventory, normalize.Inventory) else inventory.lesions.values()
    return next(item for item in lesions if item['id'] == lid)


def relations_of(inventory, statement: str = '', event: str = '') -> list:
    found = inventory.events['relations'] if isinstance(inventory, normalize.Inventory) else inventory.relations
    return [item for item in found if (not statement or item['statement'] == statement)
            and (not event or item['event'] == event)]


def snare(eid: str = 'E1', passage: str = 'P1', **changes) -> dict:
    """A cold snare removal stated in ``passage`` (its status words "was removed with a cold snare")."""
    options = {'status_words': 'was removed with a cold snare', 'technique': a('cold_snare', 'cold snare', [passage])}
    options.update(changes)
    return act(eid, passage, 'snare', 'removed', **options)


# --- distinctness (6.3; C-11; C-15) -------------------------------------------------------------------------------------

def pair_of(first: dict, second: dict, lines: dict) -> tuple:
    """(distinct_from, possibly_same_as) of the first lesion after identity.distinguish."""
    draft = built(lines, steps=[identity.distinguish], lesions=[first, second])
    record = lesion(draft, first['id'])
    return record['distinct_from'], record['possibly_same_as']


DISTINCT, SAME = (['L2'], []), ([], ['L2'])


class Distinctness(SimpleTestCase):
    def assert_pair(self, expected, first, second, lines, reason=''):
        self.assertEqual(pair_of(first, second, lines), expected)
        if reason:
            draft = built(lines, lesions=[first, second])
            facts = identity.lesion_facts(draft)
            self.assertEqual(identity.distinct_reason(facts['L1'], facts['L2']), reason)

    def test_disjoint_landmarks(self):
        lines = {'P1': 'A sessile polyp was seen in the cecum.', 'P2': 'A sessile polyp was seen in the rectum.'}
        self.assert_pair(DISTINCT, les('L1', 'sessile polyp', 'P1', landmark='cecum', site_words='cecum'),
                         les('L2', 'sessile polyp', 'P2', landmark='rectum', site_words='rectum'), lines, 'landmarks')

    def test_a_place_inside_another_is_never_a_difference(self):
        lines = {'P1': 'A sessile polyp was seen in the colon.', 'P2': 'A flat polyp was seen in the sigmoid colon.'}
        self.assert_pair(SAME, les('L1', 'sessile polyp', 'P1', landmark='colon', site_words='colon'),
                         les('L2', 'flat polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon'), lines)

    def test_an_altered_place_is_never_disjoint(self):
        lines = {'P1': 'A sessile polyp was seen at the anastomosis.', 'P2': 'A flat polyp was seen in the cecum.'}
        self.assert_pair(SAME, les('L1', 'sessile polyp', 'P1', landmark='anastomosis', site_words='anastomosis'),
                         les('L2', 'flat polyp', 'P2', landmark='cecum', site_words='cecum'), lines)

    def test_c15_the_colon_regions_carry_their_containment(self):
        lines = {'P1': 'Two diminutive polyps were seen in the sigmoid colon.',
                 'P2': 'A flat lesion was seen in the right colon.', 'P3': 'A flat lesion was seen in the left colon.',
                 'P4': 'A sessile lesion was seen in the proximal colon.'}
        sigmoid = les('L1', 'Two diminutive polyps', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                      multiplicity='group')
        self.assert_pair(DISTINCT, sigmoid, les('L2', 'flat lesion', 'P2', landmark='right_colon',
                                                site_words='right colon'), lines, 'landmarks')
        self.assert_pair(SAME, sigmoid, les('L2', 'flat lesion', 'P3', landmark='left_colon', site_words='left colon'),
                         lines)
        self.assert_pair(DISTINCT, sigmoid, les('L2', 'sessile lesion', 'P4', landmark='proximal_colon',
                                                site_words='proximal colon'), lines, 'landmarks')

    def test_an_unverified_site_establishes_nothing(self):
        lines = {'P1': 'A sessile polyp was seen in the cecum.', 'P2': 'A sessile polyp was seen in the rectum.'}
        self.assert_pair(SAME, les('L1', 'sessile polyp', 'P1', landmark='cecum', site_words='cecum'),
                         les('L2', 'sessile polyp', 'P2', landmark='ascending_colon', site_words='rectum'), lines)

    def test_distances(self):
        lines = {'P1': 'A sessile polyp was seen in the sigmoid colon at 25 cm.',
                 'P2': 'A flat polyp was seen in the sigmoid colon at 30 cm.',
                 'P3': 'A pale polyp was seen in the sigmoid colon at 30 cm from the anal verge.'}
        first = les('L1', 'sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon at 25 cm')
        self.assert_pair(DISTINCT, first, les('L2', 'flat polyp', 'P2', landmark='sigmoid_colon',
                                              site_words='sigmoid colon at 30 cm'), lines, 'distances')
        shared = les('L1', 'flat polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon at 30 cm')
        self.assert_pair(SAME, shared, les('L2', 'pale polyp', 'P3', landmark='sigmoid_colon',
                                           site_words='sigmoid colon at 30 cm'), lines)

    def test_specimen_labels(self):
        lines = {'P1': 'A sessile polyp (specimen A) was seen.', 'P2': 'A flat polyp (specimen B) was seen.',
                 'P3': 'A pale polyp (specimen A) was seen.'}
        self.assert_pair(DISTINCT, les('L1', 'sessile polyp (specimen A)', 'P1'),
                         les('L2', 'flat polyp (specimen B)', 'P2'), lines, 'specimens')
        self.assert_pair(SAME, les('L1', 'sessile polyp (specimen A)', 'P1'),
                         les('L2', 'pale polyp (specimen A)', 'P3'), lines)

    def test_c11_sizes_beyond_the_tolerance_with_nothing_shared_saying_same(self):
        lines = {'P1': 'A 3 mm polyp was seen.', 'P2': 'A 9 mm polyp was seen in the sigmoid colon.'}
        self.assert_pair(DISTINCT, les('L1', '3 mm polyp', 'P1', size_words='3 mm'),
                         les('L2', '9 mm polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                             size_words='9 mm'), lines, 'sizes')

    def test_c11_a_size_within_the_tolerance_is_no_difference(self):
        # the refuter's case: one polyp registered twice, 9 mm in the findings and 1 cm in the impression
        lines = {'P1': 'In the sigmoid colon a 9 mm sessile polyp was removed with a cold snare.',
                 'P2': 'Impression: 1 cm sessile sigmoid polyp, not removed.'}
        self.assert_pair(SAME, les('L1', '9 mm sessile polyp', 'P1', landmark='sigmoid_colon',
                                   site_words='sigmoid colon', size_words='9 mm'),
                         les('L2', '1 cm sessile sigmoid polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid',
                             size_words='1 cm'), lines)
        lines = {'P1': 'A 20 mm polyp was seen.', 'P2': 'A 25 mm polyp was seen.', 'P3': 'A 26 mm polyp was seen.'}
        self.assert_pair(SAME, les('L1', '20 mm polyp', 'P1', size_words='20 mm'),
                         les('L2', '25 mm polyp', 'P2', size_words='25 mm'), lines)  # 5 mm is 20% of 25: not beyond
        self.assert_pair(DISTINCT, les('L1', '20 mm polyp', 'P1', size_words='20 mm'),
                         les('L2', '26 mm polyp', 'P3', size_words='26 mm'), lines, 'sizes')

    def test_c11_one_verified_site_on_both_says_same(self):
        lines = {'P1': 'A 3 mm polyp was seen in the sigmoid colon.', 'P2': 'A 9 mm polyp was seen in the sigmoid colon.'}
        self.assert_pair(SAME, les('L1', '3 mm polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                                   size_words='3 mm'),
                         les('L2', '9 mm polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                             size_words='9 mm'), lines)

    def test_c11_a_shared_distance_says_same(self):
        lines = {'P1': 'A 3 mm polyp was seen at 30 cm.', 'P2': 'A 9 mm polyp was seen at 30 cm.'}
        self.assert_pair(SAME, les('L1', '3 mm polyp was seen at 30 cm', 'P1', size_words='3 mm'),
                         les('L2', '9 mm polyp was seen at 30 cm', 'P2', size_words='9 mm'), lines)
        self.assert_pair(DISTINCT, les('L1', '3 mm polyp', 'P1', size_words='3 mm'),
                         les('L2', '9 mm polyp', 'P2', size_words='9 mm'), lines, 'sizes')  # the twin: no distance read

    def test_c11_a_site_named_in_both_descriptions_says_same(self):
        # review finding 3, probe B2: no site attribute on either lesion, but each description names the sigmoid colon;
        # a site literal is read where a distance is (the site's words and the description's), so it says "same"
        lines = {'P1': 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.',
                 'P2': 'Impression: 1 cm sessile polyp in the sigmoid colon, not removed.'}
        self.assert_pair(SAME, les('L1', '6 mm sessile polyp in the sigmoid colon', 'P1', size_words='6 mm'),
                         les('L2', '1 cm sessile polyp in the sigmoid colon', 'P2', size_words='1 cm'), lines)
        # one lesion's verified site and the other's description name it: the same
        self.assert_pair(SAME, les('L1', '6 mm sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                                   size_words='6 mm'),
                         les('L2', '1 cm sessile polyp in the sigmoid colon', 'P2', size_words='1 cm'), lines)
        # the twin: descriptions naming places set apart say nothing is the same - the sizes decide
        lines = {'P1': 'A 6 mm sessile polyp in the sigmoid colon was removed.', 'P2': 'A 1 cm sessile polyp in the cecum.'}
        self.assert_pair(DISTINCT, les('L1', '6 mm sessile polyp in the sigmoid colon', 'P1', size_words='6 mm'),
                         les('L2', '1 cm sessile polyp in the cecum', 'P2', size_words='1 cm'), lines, 'sizes')

    def test_c11_compatible_sites_say_same(self):
        # review finding 3, probe B1: the left colon holds the sigmoid colon, so the two places can be one
        lines = {'P1': 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.',
                 'P2': 'Impression: 1 cm sessile polyp in the left colon, not removed.'}
        self.assert_pair(SAME, les('L1', '6 mm sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                                   size_words='6 mm'),
                         les('L2', '1 cm sessile polyp', 'P2', landmark='left_colon', site_words='left colon',
                             size_words='1 cm'), lines)

    def test_partly_shared_distances_or_specimen_labels_are_no_difference(self):
        # review finding 5, mutant (e): only lists that share NOTHING establish distinctness
        lines = {'P1': 'A flat polyp was seen at 25 cm and again at 30 cm.',
                 'P2': 'A pale polyp was seen at 30 cm and at 35 cm.'}
        self.assert_pair(SAME, les('L1', 'flat polyp was seen at 25 cm and again at 30 cm', 'P1'),
                         les('L2', 'pale polyp was seen at 30 cm and at 35 cm', 'P2'), lines)
        lines = {'P1': 'A flat polyp (specimen A, specimen B) was seen.', 'P2': 'A pale polyp (specimen B, specimen C).'}
        self.assert_pair(SAME, les('L1', 'flat polyp (specimen A, specimen B)', 'P1'),
                         les('L2', 'pale polyp (specimen B, specimen C)', 'P2'), lines)
        lines = {'P1': 'A flat polyp (specimen A, specimen B) was seen.', 'P2': 'A pale polyp (specimen C, specimen D).'}
        self.assert_pair(DISTINCT, les('L1', 'flat polyp (specimen A, specimen B)', 'P1'),
                         les('L2', 'pale polyp (specimen C, specimen D)', 'P2'), lines, 'specimens')

    def test_size_ranges_compare_by_their_nearest_ends(self):
        lines = {'P1': 'A 5-7 mm polyp was seen.', 'P2': 'An 8 mm polyp was seen.', 'P3': 'A 10 mm polyp was seen.'}
        self.assert_pair(SAME, les('L1', '5-7 mm polyp', 'P1', size_words='5-7 mm'),
                         les('L2', '8 mm polyp', 'P2', size_words='8 mm'), lines)
        self.assert_pair(DISTINCT, les('L1', '5-7 mm polyp', 'P1', size_words='5-7 mm'),
                         les('L2', '10 mm polyp', 'P3', size_words='10 mm'), lines, 'sizes')

    def test_separate_entries_of_one_passage(self):
        lines = {'P1': 'There were two polyps: a sessile polyp and a pedunculated polyp.'}
        self.assert_pair(DISTINCT, les('L1', 'sessile polyp', 'P1'), les('L2', 'pedunculated polyp', 'P1'), lines,
                         'passage')
        self.assert_pair(SAME, les('L1', 'sessile polyp', 'P1', multiplicity='group'),
                         les('L2', 'pedunculated polyp', 'P1'), lines)  # a group may hold the other
        lines = {'P1': 'A sessile polyp was seen; the polyp was flat.'}
        self.assert_pair(SAME, les('L1', 'sessile polyp', 'P1'), les('L2', 'the polyp', 'P1'), lines)  # a reference

    def test_one_passage_means_one_of_each_lesions_own_passages(self):
        line = 'A sessile polyp was seen in one segment while a pedunculated polyp was seen in another.'
        value, text = answer({'P1': line})
        value['passages'] += [{'id': 'P2', 'text': 'A sessile polyp was seen in one segment'},
                              {'id': 'P3', 'text': 'a pedunculated polyp was seen in another'}]

        def lists(first_passage: str, second_passage: str) -> tuple:
            value['lesions'] = [les('L1', 'sessile polyp', first_passage), les('L2', 'pedunculated polyp',
                                                                                  second_passage)]
            with mock.patch.object(normalize, 'LINKED_STEPS', ()):
                draft = normalize.Draft(accepted(value), text)
                draft.build()
            identity.distinguish(draft)
            return draft.lesions['L1']['distinct_from'], draft.lesions['L1']['possibly_same_as']

        self.assertEqual(lists('P2', 'P3'), SAME)  # P1 holds both descriptions, but neither lesion cites it
        self.assertEqual(lists('P1', 'P1'), DISTINCT)  # both cite P1: the registry split one passage

    def test_no_literal_means_possibly_the_same(self):
        lines = {'P1': 'A sessile polyp was seen.', 'P2': 'A flat polyp was seen.'}
        self.assert_pair(SAME, les('L1', 'sessile polyp', 'P1'), les('L2', 'flat polyp', 'P2'), lines)

    def test_the_lists_keep_the_answers_order(self):
        lines = {'P1': 'A polyp was seen in the cecum.', 'P2': 'A polyp was seen in the rectum.',
                 'P3': 'A polyp was seen in the colon.'}
        draft = built(lines, steps=[identity.distinguish],
                      lesions=[les('L1', 'polyp', 'P1', landmark='cecum', site_words='cecum'),
                               les('L2', 'polyp', 'P2', landmark='rectum', site_words='rectum'),
                               les('L3', 'polyp', 'P3', landmark='colon', site_words='colon')])
        # the rectum lies outside the colon's containment (lexicon.CONTAINS), so it is disjoint from both
        self.assertEqual([(item['distinct_from'], item['possibly_same_as']) for item in draft.lesions.values()],
                         [(['L2'], ['L3']), (['L1', 'L3'], []), (['L2'], ['L1'])])


# --- reading words (EB1) -----------------------------------------------------------------------------------------------

class Words(SimpleTestCase):
    def test_content_tokens(self):
        self.assertEqual(identity.content_tokens('Two superficial erosions at the anastomotic rim'),
                         frozenset({'superficial', 'erosion', 'anastomotic', 'rim'}))
        self.assertEqual(identity.content_tokens('it, them and these'), frozenset())
        self.assertEqual(identity.content_tokens('the mass'), frozenset({'mass'}))  # "ss" is not a plural
        self.assertEqual(identity.content_tokens('cold-snare'), frozenset({'cold', 'snare'}))

    def test_the_reference_words_are_the_lexicons_closed_list(self):
        self.assertEqual(identity._REFERENCE_NOUNS, frozenset({'lesion', 'polyp', 'mass', 'area'}))
        self.assertEqual(identity._REFERENCE_PRONOUNS, frozenset({'it', 'its', 'this', 'these', 'that', 'those', 'them'}))
        self.assertFalse(identity.reference_only('they'))  # not on the list: a known limit, widened only by a version

    def test_reference_only(self):
        for text in ('it', 'the polyps', 'the 7 mm lesion', 'the sigmoid polyp at 30 cm', 'the mass in the cecum',
                     'this area'):
            with self.subTest(text):
                self.assertTrue(identity.reference_only(text))
        for text in ('an inflamed portion of the rim', 'the pedunculated polyp', 'two superficial erosions'):
            with self.subTest(text):
                self.assertFalse(identity.reference_only(text))

    def test_specimen_labels(self):
        self.assertEqual(identity.specimen_labels('polyp (Specimen A), sent in jar 2 and bottle #3'), ('a', '2', '3'))
        self.assertEqual(identity.specimen_labels('specimen sent to pathology'), ())


# --- identity (6.2) ----------------------------------------------------------------------------------------------------

def linked(lines: dict, events: list, lesions: list, **options) -> normalize.Draft:
    return built(lines, steps=[identity.distinguish, identity.link], events=events, lesions=lesions, **options)


def identity_of(draft, eid: str = 'E1') -> tuple:
    target = ev(draft, eid)['target']
    return target['identity'], (target['identity_by'] or {}).get('reasons')


ONE = {'P1': 'A 6 mm sessile polyp in the cecum was removed with a cold snare.'}
L_ONE = les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum', size_words='6 mm')


class StatementTie(SimpleTestCase):
    def test_target_words_in_the_acts_own_statement(self):
        draft = linked(ONE, [snare(target=tg('L1', 'cecum', '6 mm sessile polyp in the cecum', ['P1']))], [L_ONE])
        self.assertEqual(identity_of(draft), ('verified', []))
        self.assertEqual(ev(draft, 'E1')['target']['identity_by']['by'],
                         {'statement': 'target_words', 'tie': 'content_word', 'literals': 'consistent',
                          'discrimination': 'only', 'lesion': 'verified'})

    def test_target_words_from_another_sentence(self):
        lines = {'P1': 'A 6 mm sessile polyp was seen in the cecum.', 'P2': 'It was removed with a cold snare.'}
        lesions = [les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum', size_words='6 mm')]
        draft = linked(lines, [snare(passage='P2', target=tg('L1', 'cecum', '6 mm sessile polyp', ['P1']))], lesions)
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_not_in_statement']))
        # the act's own statement refers back: "It"
        draft = linked(lines, [snare(passage='P2', target=tg('L1', 'not_stated', 'It', ['P2']))], lesions)
        self.assertEqual(identity_of(draft), ('verified', []))
        self.assertEqual(ev(draft, 'E1')['target']['identity_by']['by']['tie'], 'reference_words')

    def test_no_target_words_need_one_sentence_describing_the_lesion_and_stating_the_act(self):
        draft = linked(ONE, [snare(target=tg('L1'))], [L_ONE])
        self.assertEqual(identity_of(draft), ('verified', []))
        self.assertEqual(ev(draft, 'E1')['target']['identity_by']['by']['statement'], 'lesion_passage')
        lines = {'P1': 'A 6 mm sessile polyp was seen in the cecum.', 'P2': 'It was removed with a cold snare.'}
        draft = linked(lines, [snare(passage='P2', target=tg('L1'))],
                       [les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum')])
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_not_in_statement']))

    def test_target_words_that_do_not_bind_tie_to_nothing(self):
        draft = linked(ONE, [snare(target=tg('L1', 'cecum', 'the removed cecal polyp', ['P1']))], [L_ONE])
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_not_in_statement']))  # nothing else is read


class LexicalTie(SimpleTestCase):
    LINES = {'P1': 'A 6 mm sessile polyp was seen in the cecum.',
             'P2': 'Biopsies were taken from an inflamed fold of the cecal wall.'}

    def biopsy(self, words: str, landmark: str = 'not_stated') -> dict:
        return act('E1', 'P2', 'biopsy', 'Biopsies', status_words='were taken',
                   target=tg('L1', landmark, words, ['P2']))

    def test_no_shared_content_word(self):
        draft = linked(self.LINES, [self.biopsy('an inflamed fold')],
                       [les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum')])
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_no_tie']))

    def test_reference_words_and_literals_tie(self):
        lines = {'P1': 'A 6 mm sessile polyp was seen in the cecum.', 'P2': 'Biopsies were taken from the cecal lesion.'}
        draft = linked(lines, [act('E1', 'P2', 'biopsy', 'Biopsies', status_words='were taken',
                                   target=tg('L1', 'cecum', 'the cecal lesion', ['P2']))],
                       [les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum')])
        self.assertEqual(identity_of(draft), ('verified', []))
        self.assertEqual(ev(draft, 'E1')['target']['identity_by']['by']['tie'], 'reference_words')


class LiteralConsistency(SimpleTestCase):
    def run_words(self, words: str, landmark: str = 'not_stated') -> tuple:
        lines = {'P1': 'A 6 mm sessile polyp was seen in the cecum at 80 cm.',
                 'P2': f'Then {words} was removed with a cold snare.'}
        draft = linked(lines, [snare(passage='P2', target=tg('L1', landmark, words, ['P2']))],
                       [les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum at 80 cm',
                            size_words='6 mm')])
        return identity_of(draft)

    def test_size_distance_and_landmark_conflicts(self):
        self.assertEqual(self.run_words('the 9 mm polyp'), ('unresolved', ['identity_literal_conflict']))
        self.assertEqual(self.run_words('the polyp at 30 cm'), ('unresolved', ['identity_literal_conflict']))
        self.assertEqual(self.run_words('the rectal polyp', 'rectum'), ('unresolved', ['identity_literal_conflict']))

    def test_consistent_literals(self):
        self.assertEqual(self.run_words('the 6 mm polyp'), ('verified', []))
        self.assertEqual(self.run_words('the polyp at 80 cm'), ('verified', []))
        self.assertEqual(self.run_words('the colon polyp', 'colon'), ('verified', []))  # the colon holds the cecum


class Discrimination(SimpleTestCase):
    def test_two_polyps_and_a_bare_reference_are_ambiguous_unless_adjacent(self):
        lines = {'P1': 'A sessile polyp was seen in the cecum.', 'P2': 'A sessile polyp was seen in the rectum.',
                 'P3': 'The polyp was removed with a cold snare.'}
        lesions = [les('L1', 'sessile polyp was seen in the cecum', 'P1'),
                   les('L2', 'sessile polyp was seen in the rectum', 'P2')]
        far = linked(lines, [snare(passage='P3', target=tg('L1', 'not_stated', 'The polyp', ['P3']))], lesions)
        self.assertEqual(identity_of(far), ('unresolved', ['identity_ambiguous']))
        near = linked(lines, [snare(passage='P3', target=tg('L2', 'not_stated', 'The polyp', ['P3']))], lesions)
        self.assertEqual(identity_of(near), ('verified', []))
        self.assertEqual(ev(near, 'E1')['target']['identity_by']['by']['discrimination'], 'adjacency')

    def test_a_literal_or_a_content_word_of_one_lesion_alone(self):
        lines = {'P1': 'A pedunculated polyp was seen in the cecum.', 'P2': 'A sessile polyp was also seen.',
                 'P3': 'The cecal polyp was removed with a cold snare.',
                 'P4': 'The pedunculated polyp was removed with a cold snare.'}
        lesions = [les('L1', 'pedunculated polyp', 'P1', landmark='cecum', site_words='cecum'),
                   les('L2', 'sessile polyp', 'P2')]
        draft = linked(lines, [snare(passage='P3', target=tg('L1', 'cecum', 'The cecal polyp', ['P3'])),
                               snare('E2', passage='P4', target=tg('L1', 'not_stated', 'The pedunculated polyp',
                                                                   ['P4']))],
                       lesions)
        self.assertEqual(identity_of(draft, 'E1'), ('verified', []))
        self.assertEqual(ev(draft, 'E1')['target']['identity_by']['by']['discrimination'], 'literal')
        self.assertEqual(identity_of(draft, 'E2'), ('verified', []))
        self.assertEqual(ev(draft, 'E2')['target']['identity_by']['by']['discrimination'], 'content_word')

    def test_every_tied_lesion_must_be_told_apart(self):
        # review finding 5, mutant (b): a content word sets the target apart from the sessile polyp, but not from a
        # second pedunculated polyp, which is the nearer description: ambiguous
        lines = {'P1': 'A pedunculated polyp was seen in the cecum.', 'P2': 'A sessile polyp was also seen.',
                 'P3': 'A second pedunculated polyp was seen.', 'P4': 'The pedunculated polyp was removed with a cold snare.'}
        lesions = [les('L1', 'pedunculated polyp', 'P1', landmark='cecum', site_words='cecum'),
                   les('L2', 'sessile polyp', 'P2'), les('L3', 'pedunculated polyp', 'P3')]
        draft = linked(lines, [snare(passage='P4', target=tg('L1', 'not_stated', 'The pedunculated polyp', ['P4']))],
                       lesions)
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_ambiguous']))
        draft = linked(lines, [snare(passage='P4', target=tg('L3', 'not_stated', 'The pedunculated polyp', ['P4']))],
                       lesions)
        self.assertEqual(identity_of(draft), ('verified', []))  # the twin: the nearest description is adjacency's
        self.assertEqual(ev(draft, 'E1')['target']['identity_by']['by']['discrimination'], 'adjacency')

    def test_adjacency_is_never_a_tie(self):
        # review finding 5, mutant (c): the target words overlap both descriptions - both are nearest, neither alone
        lines = {'P1': 'The sessile polyp and a second sessile polyp were removed with a cold snare.'}
        lesions = [les('L1', 'sessile polyp', 'P1'), les('L2', 'second sessile polyp', 'P1')]
        both = snare(status_words='were removed with a cold snare',
                     target=tg('L1', 'not_stated', 'The sessile polyp and a second sessile polyp', ['P1']))
        draft = linked(lines, [both], lesions)
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_ambiguous']))

    def test_adjacency_needs_located_passages(self):
        lines = {'P1': 'A flat polyp was seen in the cecum.', 'P2': 'A flat polyp was seen in the rectum.',
                 'P3': 'The polyp was removed with a cold snare.'}
        text_lines = dict(lines, P4='The polyp was removed with a cold snare.')  # P3's text twice: ambiguous
        lesions = [les('L1', 'flat polyp was seen in the cecum', 'P1'), les('L2', 'flat polyp was seen in the rectum',
                                                                          'P2')]
        value, text = answer(text_lines, events=[snare(passage='P3', target=tg('L2', 'not_stated', 'The polyp',
                                                                               ['P3']))], lesions=lesions)
        value['passages'] = [item for item in value['passages'] if item['id'] != 'P4']
        with mock.patch.object(normalize, 'LINKED_STEPS', ()):
            draft = normalize.Draft(accepted(value), text)
            draft.build()
        identity.distinguish(draft)
        identity.link(draft)
        self.assertEqual(draft.passages['P3']['state'], 'ambiguous')
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_ambiguous']))

    def test_no_target_words_and_two_lesions_described_in_the_act_sentence(self):
        lines = {'P1': 'A sessile polyp and a flat polyp in the cecum were removed with a cold snare.'}
        both = act('E1', 'P1', 'snare', 'removed', status_words='were removed with a cold snare',
                   technique=a('cold_snare', 'cold snare', ['P1']), target=tg('L1'))
        draft = linked(lines, [both], [les('L1', 'sessile polyp', 'P1'), les('L2', 'flat polyp', 'P1')])
        self.assertEqual(identity_of(draft), ('unresolved', ['identity_ambiguous']))
        lines = {'P1': 'A sessile polyp in the cecum was removed with a cold snare.', 'P2': 'A flat polyp was seen.'}
        draft = linked(lines, [snare(target=tg('L1'))], [les('L1', 'sessile polyp', 'P1'), les('L2', 'flat polyp', 'P2')])
        self.assertEqual(identity_of(draft), ('verified', []))  # the other lesion is not in the act's statement


class LesionVerified(SimpleTestCase):
    def test_an_unverified_lesion(self):
        draft = linked(ONE, [snare(target=tg('L1', 'cecum', '6 mm sessile polyp in the cecum', ['P1']))],
                       [les('L1', 'sessile polyp of the cecum', 'P1', landmark='cecum', site_words='cecum')])
        self.assertEqual(lesion(draft, 'L1')['state'], 'unverified')
        reasons = identity_of(draft)[1]
        self.assertIn('lesion_unverified', reasons)


class TargetThroughLesion(SimpleTestCase):
    """S16 repair round 2: a target whose words name no landmark ("It": landmark_missing and nothing else) is verified
    through its lesion when the act is verified to be done on it and that lesion's own site is verified - the target's
    landmark that site, or one holding it. The lesion's own verified attribute is read, never a passage."""
    LINES = {'P1': 'A 6 mm sessile polyp was seen in the sigmoid colon.', 'P2': 'It was removed with a cold snare.'}
    SIGMOID = les('L1', '6 mm sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                  size_words='6 mm')

    def target(self, landmark: str = 'sigmoid_colon', lesions=None, lines=None, **options) -> tuple:
        draft = linked(lines or self.LINES, [snare(passage='P2', target=tg('L1', landmark, 'It', ['P2']))],
                       lesions or [self.SIGMOID], **options)
        record = ev(draft, 'E1')['target']
        return record['identity'], record['state'], record['reasons'], 'lesion_site' in record['checks']

    def test_a_reference_to_the_verified_lesion_takes_its_verified_site(self):
        through = ('verified', 'verified', [], True)
        self.assertEqual(self.target(), through)
        self.assertEqual(self.target('colon'), through)  # the colon holds the sigmoid colon
        self.assertEqual(self.target('left_colon'), through)  # and so does the left colon (C-15)

    def test_a_landmark_the_site_does_not_establish_stays_unverified(self):
        missing = ('verified', 'unverified', ['landmark_missing'], False)
        self.assertEqual(self.target('descending_colon'), missing)  # another place
        colon = les('L1', '6 mm sessile polyp', 'P1', landmark='colon', site_words='colon', size_words='6 mm')
        lines = {'P1': 'A 6 mm sessile polyp was seen in the colon.', 'P2': 'It was removed with a cold snare.'}
        self.assertEqual(self.target('sigmoid_colon', [colon], lines), missing)  # more specific than the site

    def test_an_unverified_site_or_an_unresolved_identity_establishes_nothing(self):
        unstated = les('L1', '6 mm sessile polyp', 'P1', landmark='sigmoid_colon', size_words='6 mm')  # no site words
        self.assertEqual(self.target(lesions=[unstated]), ('verified', 'unverified', ['landmark_missing'], False))
        lines = {'P1': 'A 6 mm sessile polyp and a 4 mm flat polyp were seen in the sigmoid colon.',
                 'P2': 'It was removed with a cold snare.'}
        two = [les('L1', '6 mm sessile polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                   size_words='6 mm'),
               les('L2', '4 mm flat polyp', 'P1', landmark='sigmoid_colon', site_words='sigmoid colon',
                   size_words='4 mm')]
        self.assertEqual(self.target(lesions=two, lines=lines), ('unresolved', 'unverified', ['landmark_missing'],
                                                                 False))

    def test_an_open_target_stays_open(self):
        question = {'about': 'target', 'events': ['E1'], 'lesions': [], 'passages': ['P2']}
        self.assertEqual(self.target(open_questions=[question]),
                         ('verified', 'unverified', ['landmark_missing'], False))

    def test_only_words_that_name_no_landmark_are_completed_by_the_site(self):
        site = {'value': 'sigmoid_colon', 'state': 'verified', 'open': False}
        for reasons in (['landmark_conflict'], ['landmark_missing', 'landmark_conflict'], ['words_unlocated']):
            with self.subTest(reasons=reasons):
                target = {'value': 'sigmoid_colon', 'state': 'unverified', 'open': False, 'reasons': list(reasons),
                          'checks': ['landmark_words']}
                identity.through_lesion(target, {'site': site})
                self.assertEqual((target['state'], target['reasons']), ('unverified', reasons))
        target = {'value': 'sigmoid_colon', 'state': 'unverified', 'open': False, 'reasons': ['landmark_missing'],
                  'checks': ['landmark_words']}
        identity.through_lesion(target, {'site': site})  # the control: the same target with landmark_missing alone
        self.assertEqual((target['state'], target['reasons'], target['checks']),
                         ('verified', [], ['landmark_words', 'lesion_site']))


class OpenAndUntouched(SimpleTestCase):
    def test_an_open_identity_question_leaves_it_unresolved(self):
        draft = linked(ONE, [snare(target=tg('L1', 'cecum', '6 mm sessile polyp in the cecum', ['P1']))], [L_ONE],
                       open_questions=[{'about': 'identity', 'events': ['E1'], 'lesions': ['L1'], 'passages': ['P1']}])
        self.assertEqual(identity_of(draft), ('unresolved', []))
        self.assertTrue(ev(draft, 'E1')['target']['identity_by']['open'])

    def test_an_undefined_lesion_and_no_lesion_are_left_as_normalize_set_them(self):
        draft = linked(ONE, [snare(target=tg('L7', 'cecum', '6 mm sessile polyp in the cecum', ['P1'])),
                             snare('E2', target=tg('', 'cecum', 'cecum', ['P1']))], [L_ONE])
        self.assertEqual(ev(draft, 'E1')['target']['identity'], 'none')
        self.assertEqual(ev(draft, 'E1')['target']['identity_by'], {'reasons': ['lesion_unknown']})
        self.assertEqual((ev(draft, 'E2')['target']['identity'], ev(draft, 'E2')['target']['identity_by']),
                         ('none', None))

    def test_the_report_counts_identity_reasons(self):
        lines = {'P1': 'A 6 mm sessile polyp was seen in the cecum.', 'P2': 'It was removed with a cold snare.'}
        inventory = normalized(lines, events=[snare(passage='P2', target=tg('L1', 'cecum', '6 mm sessile polyp',
                                                                             ['P1']))],
                               lesions=[les('L1', '6 mm sessile polyp', 'P1', landmark='cecum', site_words='cecum')])
        self.assertEqual(inventory.verification['reasons'].get('identity_not_in_statement'), 1)
        self.assertTrue(set(verify.IDENTITY_REASONS) >= {'identity_not_in_statement'})


if __name__ == '__main__':  # pragma: no cover
    sys.exit('Run with manage.py test.')
