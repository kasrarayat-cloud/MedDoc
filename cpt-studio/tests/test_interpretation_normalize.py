"""Normalization into the event inventory (Gemini migration slice S02; design/contract.md 4-5, design/FINAL.md C1-C2,
design/ADJUDICATION.md EB1-EB4), TEXT-ONLY: passages located by the participants' Locator with the closing-bracket rule;
words bound to their OWN passages by the exact and the normalized tier (C2); the three bases and the default fallback;
every structural rule of 5.4; reach, visit facts and anatomy; the date of service and its roles (8.1); the open
questions; the derived facts (8.3); the EB pins (a date in purpose words never fails the time default; a referring
physician named in the passage never fails the performer default); no merge or drop; no model-written string stored
(P9); sha256 stability; normalization DB-free under bounded.run_bounded; the seam to slice S03's steps; the store round
trip; and every closed-list reason reachable. Synthetic answers built in code and read by read.read; nothing is sent.

The steps of slice S03 (LINKED_STEPS) do not exist in this slice: each test runs normalize with them replaced by the
steps it names (none, unless it says so)."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from studio import bounded
from studio.interpretation import LABEL, normalize, read, store, verify

ENCOUNTER = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0001'
REVISION = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0002'
RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0003'
MODEL_TEXT = 'SYNTHETIC-MODEL-TEXT-S02'  # model-written text planted where it must never be stored

# A synthetic revision text (no real patient; written for this test) and the passages of the base answer.
LINES = {
    'P1': 'Synthetic colonoscopy report. Date of service: 03/14/2026.',
    'P2': 'A 7 mm sessile polyp in the transverse colon was removed with a cold snare.',
    'P3': 'No other polyp was removed.',
    'P4': 'Endoscopist: Grace Okafor, MD (fictional)',
    'P5': 'The colonoscope was advanced to the cecum.',
    'P6': 'Fellow: Robin Synthetic, MD',
}
TEXT = '\n'.join(LINES[pid] for pid in ('P1', 'P4', 'P6', 'P5', 'P2', 'P3')) + '\n'


def attr(value: str, words: str = '', passages=()) -> dict:
    return {'value': value, 'words': words, 'passages': list(passages)}


def target(lesion: str = '', landmark: str = 'not_stated', words: str = '', passages=()) -> dict:
    return {'lesion': lesion, 'landmark': landmark, 'words': words, 'passages': list(passages)}


def scope(value: str = 'not_applicable', words: str = '', passages=(), targets=()) -> dict:
    return {'value': value, 'targets': list(targets), 'words': words, 'passages': list(passages)}


def event(id: str = 'E1', **changes) -> dict:
    """A performed cold snare removal of L1 at this encounter by the documenting team (frame defaults)."""
    item = {
        'id': id,
        'procedure': attr('colonoscopy'),
        'kind': attr('snare', 'removed', ['P2']),
        'technique': attr('cold_snare', 'cold snare', ['P2']),
        'target': target('L1', 'transverse_colon', 'A 7 mm sessile polyp in the transverse colon', ['P2']),
        'time': attr('current_encounter'),
        'performer': attr('documenting_team'),
        'status': attr('performed', 'was removed with a cold snare', ['P2']),
        'scope': scope(),
        'purpose': attr('removal', 'removed', ['P2']),
        'part_of': '',
        'sequence': 0,
        'contradicts': [],
    }
    item.update(changes)
    return item


def examination(id: str = 'E0', **changes) -> dict:
    return event(id, **{'kind': attr('examination', 'colonoscope', ['P5']),
                        'technique': attr('endoscope', 'colonoscope', ['P5']), 'target': target(),
                        'status': attr('performed', 'advanced to the cecum', ['P5']),
                        'purpose': attr('not_stated'), 'sequence': 1, **changes})


def denial(id: str = 'E2', **changes) -> dict:
    return event(id, **{'kind': attr('removal', 'removed', ['P3']), 'technique': attr('not_stated'),
                        'target': target(), 'status': attr('not_performed', 'No other polyp was removed', ['P3']),
                        'scope': scope('exceptive', 'No other', ['P3']), 'purpose': attr('not_stated'), **changes})


def lesion(id: str = 'L1', **changes) -> dict:
    item = {'id': id, 'words': '7 mm sessile polyp', 'landmark': 'transverse_colon', 'site_words': 'transverse colon',
            'size_words': '7 mm', 'multiplicity': 'single', 'passages': ['P2']}
    item.update(changes)
    return item


def encounter(**changes) -> dict:
    item = {
        'date_of_service': {'value': '2026-03-14', 'state': 'stated', 'words': '03/14/2026', 'passages': ['P1'],
                            'other_dates': []},
        'documenting_endoscopist': {'words': 'Grace Okafor, MD (fictional)', 'passages': ['P4']},
        'team': [{'words': 'Robin Synthetic, MD', 'passages': ['P6']}],
        'anatomy': [],
        'reach': [{'event': 'E0', 'landmark': 'cecum', 'words': 'advanced to the cecum', 'passages': ['P5'],
                   'completion': attr('complete', 'advanced to the cecum', ['P5'])}],
        'visit_facts': [],
    }
    item.update(changes)
    return item


def answer(lines=None, **changes) -> dict:
    """A synthetic, schema-valid answer over ``lines`` ({id: passage text}, LINES by default): an examination reaching
    the cecum, a cold snare removal of L1, and an exceptive denial."""
    lines = LINES if lines is None else lines
    item = {'passages': [{'id': pid, 'text': value} for pid, value in lines.items()], 'encounter': encounter(),
            'lesions': [lesion()], 'events': [examination(), event(), denial()], 'open_questions': []}
    item.update(changes)
    return item


def accepted(value: dict) -> dict:
    parsed = read.read(json.dumps(value))
    assert not isinstance(parsed, read.Refusal), parsed
    return parsed


def run(value: dict, text: str = TEXT, steps=()) -> normalize.Inventory:
    with mock.patch.object(normalize, 'LINKED_STEPS', tuple(steps)):
        return normalize.normalize(accepted(value), text)


def ev(inventory: normalize.Inventory, eid: str) -> dict:
    return next(item for item in inventory.events['events'] if item['id'] == eid)


def les(inventory: normalize.Inventory, lid: str) -> dict:
    return next(item for item in inventory.events['lesions'] if item['id'] == lid)


def passage(inventory: normalize.Inventory, pid: str) -> dict:
    return next(item for item in inventory.events['passages'] if item['id'] == pid)


def state(record: dict) -> tuple:
    return record['state'], record['basis'], record['reasons']


def doc(*lines: str) -> str:
    return '\n'.join(lines) + '\n'


def one_line(text: str, **event_changes) -> tuple:
    """A one-passage document holding ``text`` (P1) and an answer whose only event is a cold snare removal citing it,
    with no lesion, encounter facts or reach - for checking one attribute."""
    value = answer({'P1': text}, lesions=[], encounter=encounter(
        date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []},
        documenting_endoscopist={'words': '', 'passages': []}, team=[], reach=[]),
        events=[event('E1', **{'kind': attr('snare', 'removed', ['P1']), 'technique': attr('not_stated'),
                               'target': target(), 'status': attr('performed', 'removed', ['P1']),
                               'purpose': attr('not_stated'), **event_changes})])
    return value, doc(text)


class Passages(SimpleTestCase):
    def test_located_passages_are_the_revision_texts_own_slices(self):
        inventory = run(answer())
        for pid, value in LINES.items():
            record = passage(inventory, pid)
            with self.subTest(pid):
                self.assertEqual(record['state'], 'located')
                self.assertEqual(len(record['spans']), 1)
                span = record['spans'][0]
                self.assertEqual(TEXT[span['start']:span['end']], span['text'])
                self.assertEqual(span['text'], value)
                self.assertEqual((record['reason'], record['chars'], record['extended']), ('', len(value), ''))

    def test_whitespace_runs_collapse_to_locate_a_passage_across_line_breaks(self):
        text = doc('A 7 mm sessile polyp in the transverse colon was', '   removed with a cold snare.')
        value = answer({'P2': LINES['P2']}, encounter=encounter(
            date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []},
            documenting_endoscopist={'words': '', 'passages': []}, team=[], reach=[]), events=[event()])
        record = passage(run(value, text), 'P2')
        self.assertEqual(record['state'], 'located')
        self.assertIn('\n   ', record['spans'][0]['text'])

    def test_ambiguous_and_unlocated_passages(self):
        text = doc('Biopsies were taken.', 'Biopsies were taken.', 'A polyp.')
        lines = {'P1': 'Biopsies were taken.', 'P2': 'No polyp', 'P3': f'{MODEL_TEXT} not in the text'}
        value, _ = one_line('Biopsies were taken.')
        value['passages'] = [{'id': pid, 'text': value_} for pid, value_ in lines.items()]
        inventory = run(value, text)
        ambiguous = passage(inventory, 'P1')
        self.assertEqual((ambiguous['state'], len(ambiguous['spans'])), ('ambiguous', 2))
        too_short = passage(inventory, 'P2')
        self.assertEqual((too_short['state'], too_short['spans'], too_short['reason'], too_short['chars']),
                         ('unlocated', [], 'too short', 8))
        missing = passage(inventory, 'P3')
        self.assertEqual((missing['state'], missing['spans'], missing['reason']), ('unlocated', [], 'not found'))
        self.assertEqual(missing['chars'], len(lines['P3']), 'an unlocated passage keeps its length only')
        self.assertIn('passages[1] is too short to locate in the revision text.', inventory.verification['problems'])
        self.assertIn('passages[2] was not found in the revision text.', inventory.verification['problems'])

    def test_the_closing_bracket_rule_restores_the_documents_own_closer(self):
        lines = dict(LINES, P4='Endoscopist: Grace Okafor, MD (fictional')
        record = passage(run(answer(lines)), 'P4')
        self.assertEqual((record['state'], record['extended']), ('located', 'closing_bracket'))
        self.assertEqual(record['spans'][0]['text'], 'Endoscopist: Grace Okafor, MD (fictional)')
        self.assertEqual(record['chars'], len(lines['P4']))

    def test_the_closing_bracket_rule_unit(self):
        end = normalize.closing_bracket_end
        cases = (('see (a [b])', 'see (a [b', ' ])'.strip()),  # nested, innermost first
                 ('x (synthetic )', 'x (synthetic', ' )'),  # after one run of spaces
                 ('say \u201cno further\u201d now', 'say \u201cno further', '\u201d'))
        for text, quote, closers in cases:
            with self.subTest(text):
                self.assertEqual(text[:end(text, 0, len(quote))], quote + closers)
        for text, quote in (('x (synthetic, MD)', 'x (synthetic'), ('x (a) b', 'x (a) b'),
                            ('x (a', 'x (a'), ('x (a]', 'x (a'), ('(a)) (b)', '(a)) (b'),
                            ('x (a\n)', 'x (a')):
            with self.subTest(text):
                self.assertEqual(end(text, 0, len(quote)), len(quote), 'only the exact missing closers extend a span')

    def test_the_rule_never_makes_an_unlocated_quote_locate(self):
        lines = dict(LINES, P4='Endoscopist: Grace Okafor, MD (fictional))')
        record = passage(run(answer(lines)), 'P4')
        self.assertEqual((record['state'], record['extended']), ('unlocated', ''))


class Words(SimpleTestCase):
    def test_the_exact_tier(self):
        record = ev(run(answer()), 'E1')['technique']
        self.assertEqual(record['words'], {'start': TEXT.index('cold snare'), 'end': TEXT.index('cold snare') + 10,
                                           'text': 'cold snare', 'match': 'exact', 'occurrences': 1})
        self.assertEqual(state(record), ('verified', 'stated', []))

    def test_the_normalized_tier_stores_the_documents_own_slice(self):
        for words in ('COLD SNARE', 'Cold-Snare', 'cold\u2011snare', '  cold   snare '):
            value = answer(events=[examination(), event(technique=attr('cold_snare', words, ['P2'])), denial()])
            record = ev(run(value), 'E1')['technique']
            with self.subTest(words):
                self.assertEqual(state(record), ('verified', 'stated', []))
                expected = 'exact' if words.split() == ['cold', 'snare'] else 'normalized'
                self.assertEqual((record['words']['match'], record['words']['text']), (expected, 'cold snare'))

    def test_curly_quotes_and_case_normalize(self):
        value, text = one_line('The patient said \u201cno\u201d to biopsies.',
                               status=attr('not_performed', '"No" to biopsies', ['P1']),
                               scope=scope('single_target', 'biopsies', ['P1']),
                               target=target('', 'other', 'biopsies', ['P1']))
        record = ev(run(value, text), 'E1')['status']
        self.assertEqual(record['words']['text'], '\u201cno\u201d to biopsies')
        self.assertEqual(record['words']['match'], 'normalized')

    def test_no_minimum_length_and_the_first_of_several_occurrences(self):
        value, text = one_line('No snare was used; no biopsy; no clip.', kind=attr('snare', 'snare', ['P1']),
                               status=attr('not_performed', 'no', ['P1']), scope=scope('all_of_kind', 'No', ['P1']))
        record = ev(run(value, text), 'E1')['status']
        self.assertEqual(record['words'], {'start': text.index('no biopsy'), 'end': text.index('no biopsy') + 2,
                                           'text': 'no', 'match': 'exact', 'occurrences': 2},
                         'the exact tier first: "No" is another case')
        value['events'][0]['status'] = attr('not_performed', 'NO', ['P1'])
        record = ev(run(value, text), 'E1')['status']
        self.assertEqual(record['words'], {'start': 0, 'end': 2, 'text': 'No', 'match': 'normalized',
                                           'occurrences': 3})

    def test_an_occurrence_never_splits_a_word(self):
        # "not" is in "another": substring search alone would bind a negator that is not there (S02's refinement of C2).
        value, text = one_line('Biopsies were taken from another site.', kind=attr('biopsy', 'Biopsies', ['P1']),
                               status=attr('not_performed', 'not', ['P1']), scope=scope('all_of_kind', 'Biopsies', ['P1']))
        record = ev(run(value, text), 'E1')['status']
        self.assertEqual(state(record), ('unverified', 'absent', ['words_unlocated']))
        self.assertIsNone(record['words'])

    def test_words_bind_only_inside_the_attributes_own_passages(self):
        value = answer(events=[examination(), event(technique=attr('cold_snare', 'cold snare', ['P3'])), denial()])
        record = ev(run(value), 'E1')['technique']
        self.assertEqual(state(record), ('unverified', 'absent', ['words_unlocated']),
                         'the words are in P2, which the attribute does not cite')

    def test_an_ambiguous_passage_binds_at_its_first_place(self):
        text = doc('A polyp was removed with a cold snare.', 'Impression: A polyp was removed with a cold snare.')
        value, _ = one_line('A polyp was removed with a cold snare.',
                            technique=attr('cold_snare', 'cold snare', ['P1']))
        record = ev(run(value, text), 'E1')['technique']
        self.assertEqual(record['words']['start'], text.index('cold snare'))


class Bases(SimpleTestCase):
    def test_stated_default_and_absent(self):
        inventory = run(answer())
        snare = ev(inventory, 'E1')
        self.assertEqual(state(snare['kind']), ('verified', 'stated', []))
        self.assertEqual(state(snare['time']), ('verified', 'default', []))
        self.assertEqual(state(snare['performer']), ('verified', 'default', []))
        self.assertEqual(state(snare['procedure']), ('verified', 'default', []))
        self.assertEqual(snare['procedure']['checks'], ['default', 'single_family'])
        self.assertEqual(state(snare['scope']), ('absent', 'absent', []))
        exam = ev(inventory, 'E0')
        self.assertEqual(state(exam['purpose']), ('absent', 'absent', []))
        self.assertEqual(state(exam['target']), ('absent', 'absent', []))
        for name, value in (('procedure', 'unknown'), ('technique', 'not_stated'), ('time', 'unknown'),
                            ('performer', 'unknown'), ('purpose', 'not_stated')):
            changed = answer(events=[examination(), event(**{name: attr(value, 'removed', ['P2'])}), denial()])
            record = ev(run(changed), 'E1')[name]
            with self.subTest(name):
                self.assertEqual(state(record), ('absent', 'absent', []))
                self.assertIsNone(record['words'], 'words given for a not-stated value are not bound')

    def test_a_default_value_whose_words_do_not_bind_falls_back_with_the_problem_recorded(self):
        # The time's unlocated words are a whole present-encounter frame, which denies nothing (DECISIONS D54); they
        # were f'today {MODEL_TEXT}' before D54, which now denies the default (the next test).
        value = answer(events=[examination(), event(time=attr('current_encounter', 'during this procedure', ['P2']),
                                                    performer=attr('documenting_team', 'Dr. Okafor', ['P9'])),
                               denial()])
        self.assertNotIn('during this procedure', TEXT.lower())
        inventory = run(value)
        snare = ev(inventory, 'E1')
        self.assertEqual(state(snare['time']), ('verified', 'default', []))
        self.assertEqual(snare['time']['checks'][:2], ['default', 'default_after_unlocated_words'])
        self.assertEqual(state(snare['performer']), ('verified', 'default', []))
        self.assertIn('events[1].time: its words were not found in its own passages, so the frame default was accepted.',
                      inventory.verification['problems'])

    def test_d54_unbound_current_time_words_that_are_not_whole_frames_deny_the_default(self):
        # DECISIONS D54 reads the time's given words whether or not they locate, as EB2 reads a date and D35 a marker:
        # words that are not made only of whole present-encounter frames leave the time unverified, nothing of them
        # stored. A frame beside other words, an anchor word inside them, a year: each was the default under D42.
        for words in (f'today {MODEL_TEXT}', 'These were the findings at her index colonoscopy',
                      'At the index procedure, on withdrawal', 'At her index colonoscopy in 2026'):
            value = answer(events=[examination(), event(time=attr('current_encounter', words, ['P2'])), denial()])
            snare = ev(run(value), 'E1')
            with self.subTest(words):
                self.assertEqual(state(snare['time']), ('unverified', 'absent',
                                                        ['words_unlocated', 'current_unanchored']))
                self.assertEqual((snare['time']['words'], snare['time']['literals']), (None, {}))
                self.assertEqual(snare['current'], 'unresolved')

    def test_eb2_unbound_default_words_that_deny_the_default_leave_it_unverified(self):
        # EB2 governs over 5.2's fallback: given time words holding another date, or performer words naming someone
        # who is not on the team, deny the default whether or not they locate; nothing of them is stored.
        value = answer(events=[examination(), event(time=attr('current_encounter', 'scheduled on 12/01/2026', ['P2']),
                                                    performer=attr('documenting_team', 'Dr. Patel', ['P9'])),
                               denial()])
        snare = ev(run(value), 'E1')
        # "scheduled" is also a marker of another occasion (DECISIONS D35): both readings of the words deny the default
        self.assertEqual(state(snare['time']), ('unverified', 'absent',
                                                ['words_unlocated', 'date_mismatch', 'other_occasion']))
        self.assertEqual(state(snare['performer']), ('unverified', 'absent', ['passage_unknown', 'name_mismatch']))
        for name in ('time', 'performer'):
            self.assertEqual((snare[name]['words'], snare[name]['literals']), (None, {}))
        self.assertEqual(snare['current'], 'unresolved')
        # The v5 slip's composed time words hold the service date itself: the default stands (contract 7, S4).
        composed = answer(events=[examination(), event(time=attr('current_encounter', 'today (March 14, 2026',
                                                                 ['P2'])), denial()])
        self.assertEqual(state(ev(run(composed), 'E1')['time']), ('verified', 'default', []))

    def test_any_other_value_needs_words_that_bind(self):
        cases = (('kind', attr('snare', '', ['P2']), ['words_missing']),
                 ('kind', attr('snare', 'removed', []), ['words_unlocated']),
                 ('kind', attr('snare', 'removed', ['P9']), ['passage_unknown']),
                 ('kind', attr('snare', 'resected', ['P2']), ['words_unlocated']),
                 ('time', attr('earlier_encounter', '', []), ['words_missing']),
                 ('performer', attr('other_clinician', 'Dr. Patel', ['P2']), ['words_unlocated']))
        for name, raw, reasons in cases:
            record = ev(run(answer(events=[examination(), event(**{name: raw}), denial()])), 'E1')[name]
            with self.subTest(name=name, raw=raw):
                self.assertEqual(state(record), ('unverified', 'absent', reasons))

    def test_eb1_a_target_landmark_given_with_no_words_is_never_read_from_its_passage(self):
        # EB1: the landmark row's "with empty w, a form in an own passage" is removed. P2 names the transverse colon;
        # the target gives no words, so nothing confirms its landmark (the lesion site's twin: Lesions, site and size).
        value = answer(events=[examination(), event(target=target('L1', 'transverse_colon', '', ['P2'])), denial()])
        record = ev(run(value), 'E1')['target']
        self.assertIn('transverse colon', LINES['P2'])
        self.assertEqual(state(record), ('unverified', 'absent', ['words_missing']))
        self.assertEqual((record['words'], record['literals']), (None, {}))

    def test_words_of_punctuation_alone_are_no_words(self):
        # S02's refinement of 5.2: "." holds no word, so it binds nothing (else it would bind any value).
        for words in ('.', ' \u2014 ', '()'):
            value = answer(events=[examination(), event(kind=attr('snare', words, ['P2']),
                                                        time=attr('current_encounter', words, ['P2'])), denial()])
            snare = ev(run(value), 'E1')
            with self.subTest(words):
                self.assertEqual(state(snare['kind']), ('unverified', 'absent', ['words_missing']))
                self.assertEqual(state(snare['time']), ('verified', 'default', []))
                self.assertEqual(snare['time']['checks'][:1], ['default'], 'a default, not a fallback')

    def test_an_unlocated_own_passage(self):
        lines = dict(LINES, P7=f'{MODEL_TEXT} nowhere in the document')
        value = answer(lines, events=[examination(), event(kind=attr('snare', 'removed', ['P7'])), denial()])
        record = ev(run(value), 'E1')['kind']
        self.assertEqual(state(record), ('unverified', 'absent', ['passage_unlocated']))
        both = answer(lines, events=[examination(), event(kind=attr('snare', 'removed', ['P7', 'P9'])), denial()])
        self.assertEqual(ev(run(both), 'E1')['kind']['reasons'], ['passage_unknown', 'passage_unlocated'])
        good = answer(lines, events=[examination(), event(kind=attr('snare', 'removed', ['P7', 'P2'])), denial()])
        self.assertEqual(state(ev(run(good), 'E1')['kind']), ('verified', 'stated', []),
                         'one own passage that located is enough')


class EB(SimpleTestCase):
    """ADJUDICATION EB1-EB2: the passage guards are gone; a frame default is Gemini's reading. Each pin is built so that
    the removed guard, in the shape contract 5.3 and 8.3 gave it, would have failed the default: the act's own passage
    holds a date that is not the service date (refuter C-13), or a titled name that is not on a VERIFIED team (C-14;
    with no team name verified, contract 8.3 skipped the guard's name test, so a pin without one would pin nothing)."""

    SERVICE = 'Synthetic report. Date of service: 11/09/2026.'
    TATTOO = ('A carbon-particle tattoo was placed 3 cm distal to the mass to mark it for the colectomy scheduled on '
              '12/01/2026.')
    ANASTOMOSIS = 'The anastomosis, created in 2017, was dilated with a 15 mm balloon.'
    PATEL = ('At the request of Dr. Patel, the referring gastroenterologist, random biopsies were taken from the duodenum '
             'to exclude celiac disease.')
    ENDOSCOPIST = 'Endoscopist: Grace Okafor, MD.'

    def dated(self, sentence: str, **changes):
        """``sentence`` (P1) after a stated date of service of 2026-11-09 (P0), its only event citing P1."""
        value, _ = one_line(sentence, **changes)
        value['encounter']['date_of_service'] = {'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026',
                                                 'passages': ['P0'], 'other_dates': []}
        value['passages'].insert(0, {'id': 'P0', 'text': self.SERVICE})
        return value, doc(self.SERVICE, sentence)

    def tattoo(self, **changes):
        return self.dated(self.TATTOO, **{
            'procedure': attr('colonoscopy'), 'kind': attr('tattoo', 'tattoo', ['P1']),
            'status': attr('performed', 'was placed', ['P1']),
            'purpose': attr('marking', 'to mark it for the colectomy scheduled on 12/01/2026', ['P1']), **changes})

    def patel(self, verified_team: bool, **changes):
        """The referring Dr. Patel's sentence, with (P2) or without a verified documenting endoscopist, Grace Okafor."""
        value, text = one_line(self.PATEL, **{'kind': attr('biopsy', 'random biopsies were taken', ['P1']),
                                              'status': attr('performed', 'were taken', ['P1']),
                                              'target': target('', 'duodenum', 'from the duodenum', ['P1']), **changes})
        if verified_team:
            value['encounter']['documenting_endoscopist'] = {'words': 'Grace Okafor, MD', 'passages': ['P2']}
            value['passages'].append({'id': 'P2', 'text': self.ENDOSCOPIST})
            text += self.ENDOSCOPIST + '\n'
        return value, text

    def test_a_scheduled_colectomy_date_in_purpose_words_does_not_fail_the_time_default(self):
        value, text = self.tattoo()
        inventory = run(value, text)
        tattoo = ev(inventory, 'E1')
        self.assertEqual(inventory.encounter_facts['date_of_service']['value'], '2026-11-09')
        self.assertEqual(state(tattoo['time']), ('verified', 'default', []))
        self.assertEqual(state(tattoo['purpose']), ('verified', 'stated', []))
        self.assertEqual(tattoo['current'], 'yes')

    def test_a_year_in_a_relative_clause_does_not_fail_the_time_default(self):
        # The removed guard's year arm (a year standing alone in the act's own passage; refuter C-13's second case):
        # the year dates the anastomosis, and the dilation's time is the default, with no words of its own.
        value, text = self.dated(self.ANASTOMOSIS, kind=attr('dilation', 'was dilated', ['P1']),
                                 status=attr('performed', 'was dilated', ['P1']),
                                 target=target('', 'anastomosis', 'The anastomosis', ['P1']))
        inventory = run(value, text)
        dilation = ev(inventory, 'E1')
        self.assertEqual(inventory.encounter_facts['date_of_service']['value'], '2026-11-09')
        self.assertEqual(state(dilation['time']), ('verified', 'default', []))
        self.assertEqual(state(dilation['target']), ('verified', 'stated', []))
        self.assertEqual(dilation['current'], 'yes')

    def test_but_given_time_words_holding_that_date_leave_the_time_unverified(self):
        value, text = self.tattoo(time=attr('current_encounter', 'scheduled on 12/01/2026', ['P1']))
        tattoo = ev(run(value, text), 'E1')
        # the date literal, and (DECISIONS D35) "scheduled", a marker of another occasion, each leave it unverified
        self.assertEqual(state(tattoo['time']), ('unverified', 'stated', ['date_mismatch', 'other_occasion']))
        self.assertEqual(tattoo['time']['literals'], {'dates': [{'value': '2026-12-01', 'precision': 'day'}],
                                                      'markers': ['scheduled']})
        self.assertEqual(tattoo['current'], 'unresolved')

    ORIGINAL = 'At the original procedure, a 6 mm polyp was removed with a cold snare.'

    def test_d35_given_time_words_naming_another_occasion_leave_a_current_time_unverified(self):
        # DECISIONS D35 (FRESH-2 aside-of-twins-023): "At the original procedure" given as the words of a time Gemini
        # calls current. Located in the act's own passage, they leave it unverified: a time question, never an
        # exclusion.
        value, text = self.dated(self.ORIGINAL, time=attr('current_encounter', 'At the original procedure', ['P1']))
        snare = ev(run(value, text), 'E1')
        self.assertEqual(state(snare['time']), ('unverified', 'stated', ['other_occasion']))
        self.assertEqual(snare['time']['literals'], {'markers': ['original']})
        self.assertIn('occasion_marker', snare['time']['checks'])
        self.assertEqual(snare['current'], 'unresolved')
        self.assertEqual(verify.exclusion_basis('time', snare['time']), '')
        # Unlocated, the same marker denies the default as a date literal does (EB2 reads given words, for it only).
        value, text = self.dated(self.ORIGINAL, time=attr('current_encounter', 'at the original colonoscopy', ['P1']))
        snare = ev(run(value, text), 'E1')
        self.assertEqual(state(snare['time']), ('unverified', 'absent', ['words_unlocated', 'other_occasion']))
        self.assertEqual((snare['time']['words'], snare['time']['literals']), (None, {}))

    INDEX = ('These were the findings at her index colonoscopy: a 6 mm sessile polyp in the sigmoid colon was removed '
             'with a cold snare.')
    INDEX_IN_2026 = 'At her index colonoscopy in November 2026, a 12 mm polyp was removed with a hot snare.'
    WITHDRAWAL = 'At the index procedure, on withdrawal, a 12 mm polyp was removed with a hot snare.'
    TODAY = 'Today, on withdrawal, a 6 mm polyp was removed with a cold snare.'

    def test_d54_located_current_time_words_that_are_not_whole_frames_leave_it_unverified(self):
        # DECISIONS D54 (the round-2 refutation, findings 0, 7 and 8): an anchor word inside the words ("These", "on
        # withdrawal"), or a month that holds the service date, verified these acts of the index colonoscopy as current
        # under D42. Located in the act's own passage, they now leave the time unverified: a time question, never an
        # exclusion. The whole framing sentence, as D33 asks for it, too.
        for sentence, words in ((self.INDEX, 'These were the findings at her index colonoscopy'),
                                (self.INDEX, self.INDEX),
                                (self.INDEX_IN_2026, 'At her index colonoscopy in November 2026'),
                                (self.WITHDRAWAL, 'At the index procedure, on withdrawal')):
            value, text = self.dated(sentence, time=attr('current_encounter', words, ['P1']))
            snare = ev(run(value, text), 'E1')
            with self.subTest(words):
                self.assertEqual(state(snare['time']), ('unverified', 'stated', ['current_unanchored']))
                self.assertIn('current_anchor', snare['time']['checks'])
                self.assertEqual(snare['current'], 'unresolved')
                self.assertEqual(verify.exclusion_basis('time', snare['time']), '')
        # words made only of whole present-encounter frames still verify a current time
        value, text = self.dated(self.TODAY, time=attr('current_encounter', 'Today, on withdrawal', ['P1']))
        snare = ev(run(value, text), 'E1')
        self.assertEqual(state(snare['time']), ('verified', 'stated', []))
        self.assertEqual(snare['current'], 'yes')

    def test_d35_reads_only_the_times_own_words_and_leaves_an_earlier_time_as_before(self):
        # EB1: a marker elsewhere in the passage is never read; words naming no occasion still verify a current time.
        sentence = 'Today, a 6 mm polyp was removed with a cold snare; it had previously been biopsied.'
        value, text = self.dated(sentence, time=attr('current_encounter', 'Today', ['P1']))
        snare = ev(run(value, text), 'E1')
        self.assertEqual(state(snare['time']), ('verified', 'stated', []))
        self.assertEqual(snare['current'], 'yes')
        # An earlier time worded by a C1 marker still verifies, and can still exclude (EB3 unchanged).
        value, text = self.dated('Previously, a 6 mm polyp was removed with a cold snare.',
                                 time=attr('earlier_encounter', 'Previously', ['P1']))
        snare = ev(run(value, text), 'E1')
        self.assertEqual(state(snare['time']), ('verified', 'stated', []))
        self.assertEqual(verify.exclusion_basis('time', snare['time']), 'marker')
        # "original" alone is no earlier marker: an earlier time it alone words still lacks one (a question, as before).
        value, text = self.dated(self.ORIGINAL, time=attr('earlier_encounter', 'At the original procedure', ['P1']))
        self.assertEqual(state(ev(run(value, text), 'E1')['time']), ('unverified', 'stated', ['time_marker_missing']))

    def test_a_referring_physician_named_in_the_passage_does_not_fail_the_performer_default(self):
        # The pin is the verified team (refuter C-14: "Dr. Patel is titled, is not in the team and performs no
        # event"); the document with no team is kept beside it.
        for verified_team in (True, False):
            with self.subTest(verified_team=verified_team):
                inventory = run(*self.patel(verified_team))
                okafor = [{'tokens': ['grace', 'okafor'], 'titled': False, 'credentialed': True}]
                self.assertEqual(inventory.encounter_facts['documenting_endoscopist']['names'],
                                 okafor if verified_team else [])
                biopsy = ev(inventory, 'E1')
                self.assertEqual(state(biopsy['performer']), ('verified', 'default', []))
                self.assertEqual(state(biopsy['target']), ('verified', 'stated', []))

    def test_but_given_performer_words_naming_him_leave_the_performer_unverified(self):
        biopsy = ev(run(*self.patel(True, performer=attr('documenting_team', 'Dr. Patel', ['P1']))), 'E1')
        self.assertEqual(state(biopsy['performer']), ('unverified', 'stated', ['name_mismatch']))

    def performed_by(self, words: str, endoscopist: str = 'Grace Okafor, MD', team=()):
        """A cold snare removal whose sentence (P1) names ``words`` as its performer, given as documenting_team; the
        documenting endoscopist written as ``endoscopist`` (P2) and each of ``team`` a team member (P3, ...)."""
        lines = {'P1': f'{words} removed the polyp with a cold snare.', 'P2': f'Endoscopist: {endoscopist}.'}
        lines.update({f'P{index}': f'Fellow: {member}.' for index, member in enumerate(team, 3)})
        value, _ = one_line(lines['P1'], performer=attr('documenting_team', words, ['P1']))
        value['passages'] = [{'id': pid, 'text': line} for pid, line in lines.items()]
        value['encounter']['documenting_endoscopist'] = {'words': endoscopist, 'passages': ['P2']}
        value['encounter']['team'] = [{'words': member, 'passages': [f'P{index}']}
                                      for index, member in enumerate(team, 3)]
        return ev(run(value, doc(*lines.values())), 'E1')['performer']

    def test_eb2_a_name_is_a_team_members_only_when_every_token_is_that_members(self):
        # EB2: "a name in those words that is not the documenting endoscopist or a listed team member leaves the
        # performer unverified". A token shared with the team is not enough: Dr. Michael Grace shares only Grace
        # Okafor's given name, and Dr. Grace Lee joins her given name to the fellow Robin Lee's surname.
        lee = ('Robin Lee, MD',)
        mismatch = ('unverified', 'stated', ['name_mismatch'])
        for words, team in (('Dr. Michael Grace', ()), ('Dr. Grace Lee', lee), ('Dr. Okafor and Dr. Grace Lee', lee)):
            with self.subTest(words):
                self.assertEqual(state(self.performed_by(words, team=team)), mismatch)
        for words, team in (('Dr. Okafor', ()), ('Grace Okafor', ()), ('Dr. Lee', lee),
                            ('Dr. Okafor and Dr. Lee', lee)):
            with self.subTest(words):
                self.assertEqual(state(self.performed_by(words, team=team)), ('verified', 'stated', []))

    def test_eb2_a_member_is_one_entry_so_a_surname_first_entry_stays_one_person(self):
        # The parser reads "Okafor, Grace, MD" as two names (it splits at commas); the entry is still one member, so her
        # full name in the act's words is hers, and a name joining her surname to another given name is not.
        self.assertEqual(state(self.performed_by('Grace Okafor', endoscopist='Okafor, Grace, MD')),
                         ('verified', 'stated', []))
        self.assertEqual(state(self.performed_by('Dr. Robin Okafor', endoscopist='Okafor, Grace, MD')),
                         ('unverified', 'stated', ['name_mismatch']))

    HALE = 'Both biopsies were done by Dr. Hale.'

    def hale(self, performer: str = 'documenting_team', team=(('Dr. Hale', 'P1'),),
             endoscopist=('Grace Okafor, MD', 'P2')):
        """S16 FRESH-C PAR-008 r1: a biopsy whose own sentence (P1) names Dr. Hale as its performer, the documenting
        endoscopist Grace Okafor (P2) and a fellow line (P3); each of ``team`` a team entry (words, passage)."""
        lines = {'P1': self.HALE, 'P2': 'Endoscopist: Grace Okafor, MD.', 'P3': 'Fellow: Dr. Hale.'}
        value, _ = one_line(lines['P1'], kind=attr('biopsy', 'biopsies', ['P1']),
                            status=attr('performed', 'were done', ['P1']), performer=attr(performer, 'Dr. Hale', ['P1']))
        value['passages'] = [{'id': pid, 'text': line} for pid, line in lines.items()]
        value['encounter']['documenting_endoscopist'] = {'words': endoscopist[0], 'passages': [endoscopist[1]]}
        value['encounter']['team'] = [{'words': words, 'passages': [pid]} for words, pid in team]
        return ev(run(value, doc(*lines.values())), 'E1')['performer']

    def test_eb2_a_team_entry_that_is_the_acts_own_performer_words_confirms_nothing(self):
        # Gemini listed Dr. Hale as the team FROM the very words that name him as the act's performer: that entry is
        # the act's statement again, not a document's listing of him (EB2's "listed team member"), so it confirms
        # nothing about that act and the name is not the team's.
        self.assertEqual(state(self.hale()), ('unverified', 'stated', ['name_mismatch']))
        self.assertEqual(state(self.hale(team=())), ('unverified', 'stated', ['name_mismatch']))  # (the same, unlisted)

    def test_but_a_team_entry_listed_elsewhere_still_confirms_the_name(self):
        verified = ('verified', 'stated', [])
        self.assertEqual(state(self.hale(team=(('Dr. Hale', 'P3'),))), verified)  # the fellow line lists him
        self.assertEqual(state(self.hale(team=(('Dr. Hale', 'P1'), ('Dr. Hale', 'P3')))), verified)  # either entry
        # the documenting endoscopist is never left out, even when her own words are the act's performer words
        okafor = ('Grace Okafor', 'P1')
        lines = {'P1': 'Grace Okafor removed the polyp with a cold snare.'}
        value, _ = one_line(lines['P1'], performer=attr('documenting_team', 'Grace Okafor', ['P1']))
        value['encounter']['documenting_endoscopist'] = {'words': okafor[0], 'passages': [okafor[1]]}
        self.assertEqual(state(ev(run(value, doc(lines['P1'])), 'E1')['performer']), verified)

    def test_and_another_clinicians_check_keeps_every_member(self):
        # EB3: name_not_other is never weakened - the entry naming Dr. Hale still makes "another clinician" unverified
        self.assertEqual(state(self.hale('other_clinician')), ('unverified', 'stated', ['name_not_other']))

    def test_no_inventory_ever_carries_a_removed_reason(self):
        for value, text in (self.tattoo(), self.dated(self.ANASTOMOSIS), self.patel(True), self.patel(False)):
            dumped = json.dumps(run(value, text).__dict__)
            for removed in verify.REMOVED_REASONS:
                self.assertNotIn(removed, dumped)


class PlaceFree(SimpleTestCase):
    """S16 repair round 2 as DECISIONS D37 leaves it: the technique (normalize.PLACE_FREE) cited from a passage too short
    for the Locator to place - a heading "Snare" - binds its words where that passage's text stands, the location kept
    ambiguous by its occurrences. The procedure no longer does (D37 withdrew it): a procedure cited only from a heading
    "EGD" stays unverified, as before round 3. A place-bound attribute never binds there, nor words the passage does not
    hold, nor a passage the document does not hold."""
    LINES = {'P1': 'ENDOSCOPY NOTE - EGD AND COLONOSCOPY', 'P2': 'EGD', 'P3': 'Biopsies were taken from the antrum.',
             'P4': 'COLONOSCOPY', 'P5': 'The colonoscope was advanced to the cecum.', 'P7': 'Antrum', 'P8': 'Snare',
             'P9': 'A 6 mm polyp in the sigmoid colon was removed.', 'P10': 'Device: Snare'}
    TEXT = doc(*LINES.values())

    def inventory(self, snare=None, **changes):
        colonoscopy = examination('E0', procedure=attr('colonoscopy', 'COLONOSCOPY', ['P4']))
        upper = event('E2', procedure=attr('egd', 'EGD', ['P1']), kind=attr('examination', 'ENDOSCOPY NOTE', ['P1']),
                      technique=attr('not_stated'), target=target(), status=attr('performed', 'ENDOSCOPY NOTE', ['P1']),
                      purpose=attr('not_stated'))
        biopsy = event('E1', **{'procedure': attr('egd', 'EGD', ['P2']), 'kind': attr('biopsy', 'Biopsies', ['P3']),
                                'technique': attr('not_stated'), 'target': target('', 'gastric_antrum', 'antrum', ['P3']),
                                'status': attr('performed', 'were taken', ['P3']), 'purpose': attr('not_stated'),
                                **changes})
        removal = event('E3', procedure=attr('colonoscopy', 'COLONOSCOPY', ['P4']), kind=attr('snare', 'removed', ['P9']),
                        technique=snare or attr('snare', 'Snare', ['P8']),
                        target=target('', 'sigmoid_colon', 'sigmoid colon', ['P9']),
                        status=attr('performed', 'was removed', ['P9']), purpose=attr('removal', 'removed', ['P9']))
        lines = dict(self.LINES, P6='Snares')  # P6 is in the passage table and NOT in the document
        value = answer(lines, lesions=[], events=[colonoscopy, upper, biopsy, removal], encounter=encounter(
            date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []},
            documenting_endoscopist={'words': '', 'passages': []}, team=[], reach=[]))
        return run(value, self.TEXT)

    def test_a_technique_named_by_a_heading_too_short_to_place(self):
        inventory = self.inventory()
        self.assertEqual((passage(inventory, 'P8')['state'], passage(inventory, 'P8')['reason']),
                         ('unlocated', 'too short'))  # the passage itself stays unlocated
        technique = ev(inventory, 'E3')['technique']
        self.assertEqual(state(technique), ('verified', 'stated', []))
        self.assertEqual(technique['checks'][:2], ['passage_places', 'words_in_own_passage'])
        self.assertIn('device_words', technique['checks'])  # the device check ran on the words
        words = technique['words']
        self.assertEqual((words['text'], words['occurrences']), ('Snare', 2))  # heading and device line: ambiguous
        self.assertEqual(words['start'], self.TEXT.index('Snare'))  # the first place

    def test_d37_a_procedure_named_by_a_heading_too_short_to_place_stays_unverified(self):
        # DECISIONS D37: the procedure is not place-free. Two families stand, so no default settles it either.
        inventory = self.inventory()
        self.assertEqual((passage(inventory, 'P2')['state'], passage(inventory, 'P2')['reason']),
                         ('unlocated', 'too short'))
        procedure = ev(inventory, 'E1')['procedure']
        self.assertEqual(state(procedure), ('unverified', 'absent', ['passage_unlocated', 'procedure_unsettled']))
        self.assertIsNone(procedure['words'])
        self.assertNotIn('passage_places', procedure['checks'])
        self.assertNotIn('procedure', normalize.PLACE_FREE)

    def test_a_place_bound_attribute_never_binds_there(self):
        status = ev(self.inventory(status=attr('performed', 'EGD', ['P2'])), 'E1')['status']
        self.assertEqual(state(status), ('unverified', 'absent', ['passage_unlocated']))

    def test_nor_words_the_passage_does_not_hold_nor_a_passage_the_document_does_not_hold(self):
        for technique in (attr('snare', 'Snare', ['P7']), attr('snare', 'Snares', ['P6'])):
            with self.subTest(technique['passages']):
                record = ev(self.inventory(snare=technique), 'E3')['technique']
                self.assertEqual(record['state'], 'unverified')
                self.assertIn('passage_unlocated', record['reasons'])


class Procedure(SimpleTestCase):
    TWO = doc('EGD: the esophagus was normal.', 'Colonoscopy: a polyp was removed with a cold snare.')

    def two_families(self, *events):
        lines = {'P1': 'EGD: the esophagus was normal.', 'P2': 'Colonoscopy: a polyp was removed with a cold snare.'}
        exams = [event('E0', procedure=attr('egd', 'EGD', ['P1']), kind=attr('examination', 'EGD', ['P1']),
                       technique=attr('not_stated'), target=target(), status=attr('performed', 'normal', ['P1']),
                       purpose=attr('not_stated')),
                 event('E1', procedure=attr('colonoscopy', 'Colonoscopy', ['P2']),
                       kind=attr('examination', 'Colonoscopy', ['P2']), technique=attr('not_stated'), target=target(),
                       status=attr('performed', 'removed', ['P2']), purpose=attr('not_stated'))]
        value = answer(lines, lesions=[], events=exams + list(events), encounter=encounter(
            date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []},
            documenting_endoscopist={'words': '', 'passages': []}, team=[], reach=[]))
        return run(value, self.TWO)

    def snare(self, procedure):
        return event('E2', procedure=procedure, kind=attr('snare', 'removed', ['P2']),
                     technique=attr('cold_snare', 'cold snare', ['P2']), target=target(),
                     status=attr('performed', 'removed', ['P2']), purpose=attr('not_stated'))

    def test_one_family_settles_the_default(self):
        record = ev(run(answer()), 'E1')['procedure']
        self.assertEqual(state(record), ('verified', 'default', []))

    def test_two_families_leave_the_default_unsettled(self):
        record = ev(self.two_families(self.snare(attr('colonoscopy'))), 'E2')['procedure']
        self.assertEqual(state(record), ('unverified', 'absent', ['procedure_unsettled']))
        self.assertEqual(record['checks'], ['single_family'])

    def test_two_families_need_the_claimed_name_in_the_words(self):
        named = ev(self.two_families(self.snare(attr('colonoscopy', 'Colonoscopy', ['P2']))), 'E2')['procedure']
        self.assertEqual(state(named), ('verified', 'stated', []))
        wrong = ev(self.two_families(self.snare(attr('egd', 'Colonoscopy', ['P2']))), 'E2')['procedure']
        self.assertEqual(state(wrong), ('unverified', 'stated', ['procedure_name_missing']))

    def test_unbound_words_with_no_settled_default(self):
        record = ev(self.two_families(self.snare(attr('colonoscopy', 'sigmoidoscopy', ['P2']))), 'E2')['procedure']
        self.assertEqual(record['reasons'], ['words_unlocated', 'procedure_unsettled'])

    def test_an_em_visit_takes_its_family_from_its_kind(self):
        visit = event('E3', procedure=attr('office_em'), kind=attr('em_visit', 'EGD', ['P1']),
                      technique=attr('not_stated'), target=target(), status=attr('performed', 'normal', ['P1']),
                      purpose=attr('not_stated'))
        self.assertEqual(state(ev(self.two_families(visit), 'E3')['procedure']), ('verified', 'default', []))

    def visit(self, words: str):
        return event('E3', procedure=attr('office_em', words, ['P1']), kind=attr('em_visit', 'EGD', ['P1']),
                     technique=attr('not_stated'), target=target(), status=attr('performed', 'normal', ['P1']),
                     purpose=attr('not_stated'))

    def test_an_em_visits_unlocated_words_fall_back_to_the_default_its_kind_settles(self):
        # Contract 5.2: a default value whose words do not locate falls back to the default, the problem recorded,
        # because it would have been accepted with no words at all. Only EB2's literals (a time's date, a performer's
        # names) deny a default through unlocated words; the procedure name check never reads them.
        inventory = self.two_families(self.visit('the encounter today'))
        record = ev(inventory, 'E3')['procedure']
        self.assertEqual(state(record), ('verified', 'default', []))
        self.assertEqual(record['checks'], ['default', 'default_after_unlocated_words', 'single_family'])
        self.assertIn('events[2].procedure: its words were not found in its own passages, so the frame default was '
                      'accepted.', inventory.verification['problems'])
        # Words that DO locate are the visit's stated evidence, and with two families they must name its family.
        located = ev(self.two_families(self.visit('normal')), 'E3')['procedure']
        self.assertEqual(state(located), ('unverified', 'stated', ['procedure_name_missing']))


class Structure(SimpleTestCase):
    """Contract 5.4, rule by rule."""

    def test_a_scope_on_a_positive_or_planned_event_is_discarded(self):
        for status in (attr('performed', 'was removed with a cold snare', ['P2']),
                       attr('planned', 'was removed', ['P2'])):
            value = answer(events=[examination(), event(status=status, scope=scope('single_target', 'sessile polyp',
                                                                                    ['P2'])), denial()])
            inventory = run(value)
            record = ev(inventory, 'E1')['scope']
            with self.subTest(status['value']):
                self.assertEqual((record['state'], record['reasons']), ('discarded', ['scope_not_permitted']))
                self.assertIn({'where': 'events[1].scope', 'reason': 'scope_not_permitted'},
                              inventory.verification['discarded'])

    def test_a_negative_statement_with_no_scope_gets_scope_unknown(self):
        value = answer(events=[examination(), event(), denial(scope=scope())])
        inventory = run(value)
        record = ev(inventory, 'E2')['scope']
        self.assertEqual((record['value'], record['basis'], record['state']), ('unknown', 'absent', 'absent'))
        self.assertIn('scope_permitted', record['checks'])
        self.assertTrue(any('its scope is unknown' in problem for problem in inventory.verification['problems']))

    def test_scope_target_mismatch(self):
        cases = ((scope('single_target', 'No other', ['P3']), target(), True),
                 (scope('single_target', 'No other', ['P3']), target('', 'rectum', 'polyp', ['P3']), False),
                 (scope('listed_targets', 'No other', ['P3'], ['L1']), target(), True),
                 (scope('listed_targets', 'No other', ['P3'], ['L1', 'L2']), target(), False),
                 (scope('all_of_kind', 'No other', ['P3']), target('L1', 'not_stated', 'polyp', ['P3']), True),
                 (scope('all_of_kind', 'No other', ['P3']), target(), False),
                 # a lesion id the answer never defines is still a lesion the statement is tied to (5.4:
                 # all_of_kind needs NO lesion), with or without words; single_target reads only a defined one, the
                 # conservative way
                 (scope('all_of_kind', 'No other', ['P3']), target('L9'), True),
                 (scope('all_of_kind', 'No other', ['P3']), target('L9', 'not_stated', 'polyp', ['P3']), True),
                 (scope('single_target', 'No other', ['P3']), target('L9', 'not_stated', 'polyp', ['P3']), True))
        for index, (raw_scope, raw_target, mismatch) in enumerate(cases):
            value = answer(lesions=[lesion(), lesion('L2', words='polyp', size_words='', site_words='',
                                                     landmark='not_stated', passages=['P3'])],
                           events=[examination(), event(), denial(scope=raw_scope, target=raw_target)])
            record = ev(run(value), 'E2')['scope']
            with self.subTest(index):
                self.assertEqual('scope_target_mismatch' in record['reasons'], mismatch)
                self.assertEqual(record['state'], 'unverified' if mismatch else 'verified')

    def test_a_lesion_listed_twice_is_one_target(self):
        value = answer(lesions=[lesion(), lesion('L2', words='polyp', size_words='', site_words='',
                                                 landmark='not_stated', passages=['P3'])],
                       events=[examination(), event(), denial(scope=scope('listed_targets', 'No other', ['P3'],
                                                                         ['L1', 'L1', 'L9']))])
        inventory = run(value)
        record = ev(inventory, 'E2')['scope']
        self.assertEqual(record['targets'], ['L1'])
        self.assertEqual(record['reasons'], ['scope_target_mismatch'])
        self.assertIn('events[2].scope names a lesion the answer does not define.', inventory.verification['problems'])

    def test_a_positive_intervention_umbrella(self):
        value = answer(events=[examination(), event(kind=attr('intervention', 'removed', ['P2'])), denial()])
        record = ev(run(value), 'E1')['kind']
        self.assertEqual(state(record), ('unverified', 'stated', ['umbrella_on_positive']))
        allowed = answer(events=[examination(), event(), denial(kind=attr('intervention', 'removed', ['P3']))])
        self.assertEqual(state(ev(run(allowed), 'E2')['kind']), ('verified', 'stated', []))

    def test_inconsistent_status_and_time(self):
        lines = dict(LINES, P7='A repeat colonoscopy will be performed next year.',
                     P8='A colonoscopy was planned previously.')
        text = TEXT + 'A repeat colonoscopy will be performed next year.\nA colonoscopy was planned previously.\n'
        future = event('E3', kind=attr('examination', 'colonoscopy', ['P7']), technique=attr('not_stated'),
                       target=target(), status=attr('performed', 'will be performed', ['P7']),
                       time=attr('future', 'next year', ['P7']), purpose=attr('not_stated'))
        earlier = event('E4', kind=attr('examination', 'colonoscopy', ['P8']), technique=attr('not_stated'),
                        target=target(), status=attr('planned', 'was planned', ['P8']),
                        time=attr('earlier_encounter', 'previously', ['P8']), purpose=attr('not_stated'))
        inventory = run(answer(lines, events=[examination(), event(), denial(), future, earlier]), text)
        for eid in ('E3', 'E4'):
            record = ev(inventory, eid)
            with self.subTest(eid):
                self.assertEqual(record['status']['reasons'], ['inconsistent_status_time'])
                self.assertEqual(record['time']['reasons'], ['inconsistent_status_time'])
                self.assertEqual((record['status']['state'], record['time']['state']), ('unverified', 'unverified'))

    def test_part_of(self):
        steps = [examination(), event(part_of='E0'), denial(part_of='E2'), event('E3', part_of='E4'),
                 event('E4', part_of='E3'), event('E5', part_of=MODEL_TEXT[:20])]
        inventory = run(answer(events=steps))
        self.assertEqual(state(ev(inventory, 'E1')['part_of']), ('verified', 'stated', []))
        self.assertEqual(ev(inventory, 'E1')['part_of']['value'], 'E0')
        for eid, value in (('E2', 'E2'), ('E3', 'E4'), ('E4', 'E3'), ('E5', '')):
            record = ev(inventory, eid)['part_of']
            with self.subTest(eid):
                self.assertEqual(state(record), ('unverified', 'stated', ['part_of_invalid']))
                self.assertEqual(record['value'], value, 'an undefined id is never stored')
        self.assertEqual(state(ev(inventory, 'E0')['part_of']), ('absent', 'absent', []))

    def test_an_undefined_lesion_has_no_identity(self):
        value = answer(events=[examination(), event(target=target('L9', 'transverse_colon', 'transverse colon',
                                                                  ['P2'])), denial()])
        inventory = run(value)
        record = ev(inventory, 'E1')['target']
        self.assertEqual((record['lesion'], record['identity'], record['identity_by']),
                         ('', 'none', {'reasons': ['lesion_unknown']}))
        self.assertEqual(state(record), ('verified', 'stated', []), 'the site-level target stays')
        self.assertEqual(inventory.verification['reasons']['lesion_unknown'], 1)
        defined = ev(run(answer()), 'E1')['target']
        self.assertEqual((defined['lesion'], defined['identity'], defined['identity_by']), ('L1', 'unresolved', None),
                         'identity.link decides a defined lesion')

    def test_model_claims_naming_no_other_event_are_dismissed(self):
        value = answer(events=[examination(), event(contradicts=[{'event': 'E2', 'passages': ['P3', 'P9']}]),
                               denial(contradicts=[{'event': 'E99', 'passages': ['P3']},
                                                   {'event': 'E2', 'passages': []}])])
        inventory = run(value, steps=[('tests.test_interpretation_normalize', 'keep_claims')])
        self.assertEqual(inventory.events['relations'], [
            {'id': 'R1', 'type': 'dismissed_claim', 'statement': 'E2', 'event': '', 'attribute': '',
             'reason': 'claim_unknown_event', 'claimed_by_model': True, 'passages': ['P3']},
            {'id': 'R2', 'type': 'dismissed_claim', 'statement': 'E2', 'event': '', 'attribute': '',
             'reason': 'claim_unknown_event', 'claimed_by_model': True, 'passages': []}])
        self.assertEqual(KEPT_CLAIMS[-1], [{'statement': 'E1', 'event': 'E2', 'passages': ['P3']}])
        self.assertEqual(inventory.verification['relations'], {'dismissed_claim': 2})


KEPT_CLAIMS: list = []
CALLS: list = []


def keep_claims(draft) -> None:
    KEPT_CLAIMS.append(copy.deepcopy(draft.claims))


def spy_one(draft) -> None:
    CALLS.append(('one', sorted(draft.events), sorted(draft.lesions), draft.service_date))


def spy_two(draft) -> None:
    CALLS.append(('two', len(draft.claims)))
    draft.relation('independent', statement='E2', event='E1', attribute='scope', reason='exceptive',
                   passages=['P3', 'P9'])
    draft.events['E1']['catalogue_kind'] = 'snare'
    draft.events['E1']['target']['identity'] = 'verified'
    draft.events['E1']['target']['identity_by'] = {'reasons': [], 'by': ['statement_tie']}


def spy_bad_reason(draft) -> None:
    draft.events['E1']['target']['identity_by'] = {'reasons': ['a reason of the model']}


class Reach(SimpleTestCase):
    def test_a_permitted_reach_is_the_examinations_extent(self):
        inventory = run(answer())
        exam = ev(inventory, 'E0')
        self.assertEqual(state(exam['extent']), ('verified', 'stated', []))
        self.assertEqual(exam['extent']['value'], 'cecum')
        self.assertIn('reach_permitted', exam['extent']['checks'])
        self.assertEqual(state(exam['completion']), ('verified', 'stated', []))
        self.assertEqual(inventory.encounter_facts['reach'], [
            {'event': 'E0', 'family': 'gi.colonoscopy', 'landmark': 'cecum', 'state': 'verified', 'reasons': [],
             'attached': True}])

    def refused(self, exam, reach=None, p5=None):
        """The base answer with ``exam`` as E0 (and ``reach`` as its only reach), over the base text with P5 read as
        ``p5`` when given."""
        lines, text = (LINES, TEXT) if p5 is None else (dict(LINES, P5=p5), TEXT.replace(LINES['P5'], p5))
        value = answer(lines, events=[exam, event(), denial()])
        if reach is not None:
            value['encounter']['reach'] = [reach]
        inventory = run(value, text)
        return inventory, ev(inventory, 'E0')

    EARLIER = 'Previously, the colonoscope was advanced to the cecum.'

    def earlier(self, reach=None):
        """The E5 slip: a VERIFIED earlier examination - its time words "Previously" locate in its own passage and
        carry an earlier-time marker - so a reach is refused by the time's value, never by an unusable time."""
        inventory, exam = self.refused(examination(time=attr('earlier_encounter', 'Previously', ['P5'])), reach,
                                       p5=self.EARLIER)
        self.assertEqual(state(exam['time']), ('verified', 'stated', []))
        self.assertEqual((exam['time']['literals'], exam['current']), ({'markers': ['previously']}, 'no'))
        return inventory, exam

    def test_slip_e5_a_reach_on_an_earlier_examination_is_discarded(self):
        inventory, exam = self.earlier()
        self.assertIsNone(exam['extent'])
        self.assertEqual(inventory.encounter_facts['reach'][0]['state'], 'discarded')
        self.assertIn({'where': 'encounter.reach[0]', 'reason': 'reach_not_permitted'},
                      inventory.verification['discarded'])

    def test_slip_e13_a_reach_on_an_examination_without_an_endoscope_is_discarded(self):
        for technique in (attr('manual', 'colonoscope', ['P5']), attr('not_stated')):
            with self.subTest(technique['value']):
                _, exam = self.refused(examination(technique=technique))
                self.assertIsNone(exam['extent'])

    def test_a_refused_reach_keeps_an_absent_completion_absent(self):
        inventory, exam = self.earlier({'event': 'E0', 'landmark': 'cecum', 'words': 'advanced to the cecum',
                                        'passages': ['P5'], 'completion': attr('not_stated')})
        self.assertEqual(inventory.verification['counts']['completion']['absent'], 1)
        self.assertEqual(inventory.verification['counts']['completion']['discarded'], 0)
        self.assertEqual(inventory.verification['counts']['reach']['discarded'], 1)

    def test_every_other_refusal(self):
        refusals = (examination(kind=attr('biopsy', 'colonoscope', ['P5'])),
                    examination(status=attr('planned', 'advanced to the cecum', ['P5'])),
                    examination(status=attr('performed', 'advanced', ['P3'])),  # status unverified
                    examination(technique=attr('endoscope', 'polyp', ['P2'])))  # technique unverified
        for index, exam in enumerate(refusals):
            with self.subTest(index):
                inventory, record = self.refused(exam)
                self.assertIsNone(record['extent'])
                self.assertEqual(inventory.encounter_facts['reach'][0]['state'], 'discarded')
        opened = answer(open_questions=[{'about': 'time', 'events': ['E0'], 'lesions': [], 'passages': []}])
        self.assertIsNone(ev(run(opened), 'E0')['extent'], 'an open time is not a usable current time')

    def test_not_stated_technique_with_a_scope_named_in_the_reach_words(self):
        exam = examination(technique=attr('not_stated'))
        reach = {'event': 'E0', 'landmark': 'cecum', 'words': 'The colonoscope was advanced to the cecum',
                 'passages': ['P5'], 'completion': attr('not_stated')}
        _, record = self.refused(exam, reach)
        self.assertEqual(state(record['extent']), ('verified', 'stated', []))
        self.assertEqual(state(record['completion']), ('absent', 'absent', []))

    def test_a_guidewires_reach_is_unverified(self):
        lines = dict(LINES, P5='The guidewire was advanced to the cecum.')
        text = TEXT.replace(LINES['P5'], 'The guidewire was advanced to the cecum.')
        value = answer(lines, events=[examination(technique=attr('endoscope', 'colonoscopy', ['P1'])), event(), denial()])
        value['events'][0]['kind'] = attr('examination', 'colonoscopy', ['P1'])
        value['events'][0]['status'] = attr('performed', 'advanced to the cecum', ['P5'])
        value['encounter']['reach'][0]['words'] = 'The guidewire was advanced to the cecum'
        record = ev(run(value, text), 'E0')['extent']
        self.assertEqual(state(record), ('unverified', 'stated', ['device_reach']))

    def test_eb1_the_reach_guard_reads_only_the_reach_words(self):
        # EB1: the guard reads the reach's own words, never the rest of its passage. P5 names a guidewire; the reach's
        # words do not, so the reach is Gemini's reading of the endoscope's and stays verified.
        p5 = 'The guidewire was passed and the cecum was reached.'
        exam = examination(technique=attr('endoscope', 'colonoscopy', ['P1']),
                           kind=attr('examination', 'colonoscopy', ['P1']),
                           status=attr('performed', 'the cecum was reached', ['P5']))
        reach = {'event': 'E0', 'landmark': 'cecum', 'words': 'the cecum was reached', 'passages': ['P5'],
                 'completion': attr('not_stated')}
        _, record = self.refused(exam, reach, p5=p5)
        self.assertEqual(state(record['extent']), ('verified', 'stated', []))
        self.assertIn('reach_device', record['extent']['checks'])
        # The same reach whose own words name the guidewire is a device's reach.
        _, record = self.refused(exam, dict(reach, words='The guidewire was passed and the cecum was reached'), p5=p5)
        self.assertEqual(state(record['extent']), ('unverified', 'stated', ['device_reach']))

    def test_an_unknown_event_and_a_second_reach(self):
        value = answer()
        value['encounter']['reach'] = [
            dict(value['encounter']['reach'][0], event=MODEL_TEXT[:20]),
            value['encounter']['reach'][0],
            dict(value['encounter']['reach'][0], landmark='colon', words='advanced to the cecum')]
        inventory = run(value)
        entries = inventory.encounter_facts['reach']
        self.assertEqual([(entry['event'], entry['state'], entry['attached']) for entry in entries],
                         [('', 'discarded', False), ('E0', 'verified', True), ('E0', 'verified', False)])
        self.assertEqual(ev(inventory, 'E0')['extent']['value'], 'cecum', 'the first permitted reach is kept')
        problems = inventory.verification['problems']
        self.assertIn('encounter.reach[0] names an event the answer does not define.', problems)
        self.assertIn('encounter.reach[2] gives a second reach for one examination; the first is kept.', problems)

    # DECISIONS D36: a reach is verified only from a passage of its own examination, or one no act of its session cites.
    BIOPSY = 'Biopsies of the ascending colon were taken.'

    def sourced(self, reach, *events, lines=()):
        """The base answer, its text plus ``lines`` ({id: text}, appended in order), the base events plus ``events``
        and ``reach`` as the only reach: (the inventory, E0, the reach entry)."""
        added = dict(lines)
        value = answer(dict(LINES, **added), events=[examination(), event(), denial(), *events])
        value['encounter']['reach'] = [dict({'event': 'E0', 'completion': attr('not_stated')}, **reach)]
        inventory = run(value, TEXT + ''.join(f'{text}\n' for text in added.values()))
        return inventory, ev(inventory, 'E0'), inventory.encounter_facts['reach'][0]

    def biopsy(self, id='E3', passage='P7', landmark='ascending_colon', words='ascending colon', **changes):
        """A performed biopsy of this encounter's colonoscopy, stated in ``passage``."""
        return event(id, **{'kind': attr('biopsy', 'Biopsies', [passage]), 'technique': attr('not_stated'),
                            'target': target('', landmark, words, [passage]),
                            'status': attr('performed', 'were taken', [passage]), 'purpose': attr('not_stated'),
                            **changes})

    def test_d36_the_examinations_own_statement_or_a_line_no_act_cites_verifies_a_reach(self):
        _, exam, entry = self.sourced({'landmark': 'cecum', 'words': 'advanced to the cecum', 'passages': ['P5']})
        self.assertEqual(state(exam['extent']), ('verified', 'stated', []))
        self.assertIn('reach_source', exam['extent']['checks'])
        # "Cecum reached." on a line of its own, which no event cites
        _, exam, entry = self.sourced({'landmark': 'cecum', 'words': 'Cecum reached', 'passages': ['P7']},
                                      lines={'P7': 'Cecum reached.'})
        self.assertEqual(state(exam['extent']), ('verified', 'stated', []))
        self.assertEqual((entry['state'], entry['attached']), ('verified', True))
        # a sentence the examination and an act both cite is the examination's own
        both = 'The colonoscope was advanced to the cecum, where biopsies were taken.'
        examination_ = examination(kind=attr('examination', 'colonoscope', ['P7']),
                                   status=attr('performed', 'advanced to the cecum', ['P7']))
        value = answer(dict(LINES, P7=both), events=[examination_, event(), denial(),
                                                     self.biopsy(landmark='cecum', words='cecum')])
        value['encounter']['reach'] = [{'event': 'E0', 'landmark': 'cecum', 'words': 'advanced to the cecum',
                                        'passages': ['P7'], 'completion': attr('not_stated')}]
        self.assertEqual(state(ev(run(value, TEXT + both + '\n'), 'E0')['extent']), ('verified', 'stated', []))

    def test_d36_a_reach_read_only_from_another_acts_sentence_is_inferred(self):
        inventory, exam, entry = self.sourced(
            {'landmark': 'ascending_colon', 'words': 'ascending colon', 'passages': ['P7']}, self.biopsy(),
            lines={'P7': self.BIOPSY})
        self.assertEqual(state(exam['extent']), ('unverified', 'stated', ['reach_inferred']))
        self.assertEqual(exam['extent']['checks'][-2:], ['reach_source', 'reach_permitted'])
        self.assertEqual((entry['state'], entry['reasons'], entry['attached']),
                         ('unverified', ['reach_inferred'], True))  # still the examination's: R6 reads it unverified
        self.assertEqual(inventory.verification['reasons'], {'reach_inferred': 1})
        self.assertEqual(inventory.verification['counts']['reach']['unverified'], 1)
        # citing the examination's own passage beside it changes nothing when the words stand only in the act's
        _, exam, _ = self.sourced({'landmark': 'ascending_colon', 'words': 'ascending colon', 'passages': ['P5', 'P7']},
                                  self.biopsy(), lines={'P7': self.BIOPSY})
        self.assertEqual(state(exam['extent']), ('unverified', 'stated', ['reach_inferred']))

    def test_d36_another_examination_of_the_session_is_another_event(self):
        # The reach of a prior colonoscopy, read for today's: its passage belongs to another event of the session.
        prior = 'A prior colonoscopy in 2024 reached the cecum.'
        earlier = examination('E3', kind=attr('examination', 'colonoscopy', ['P7']),
                              technique=attr('not_stated'), time=attr('earlier_encounter', 'in 2024', ['P7']),
                              status=attr('performed', 'reached the cecum', ['P7']))
        _, exam, _ = self.sourced({'landmark': 'cecum', 'words': 'reached the cecum', 'passages': ['P7']}, earlier,
                                  lines={'P7': prior})
        self.assertEqual(state(exam['extent']), ('unverified', 'stated', ['reach_inferred']))

    def test_d36_an_act_of_another_session_does_not_make_a_passage_the_sessions(self):
        # D36's scope is the examination's session (its family): an EGD act citing the line leaves it no act's of the
        # colonoscopy, so the colonoscopy's reach read there stays verified.
        line = 'Biopsies of the duodenum and the terminal ileum were taken.'
        egd = self.biopsy(procedure=attr('egd', 'Biopsies of the duodenum', ['P7']), landmark='duodenum',
                          words='duodenum')
        inventory, exam, _ = self.sourced({'landmark': 'terminal_ileum', 'words': 'terminal ileum',
                                           'passages': ['P7']}, egd, lines={'P7': line})
        self.assertEqual(ev(inventory, 'E3')['family'], 'gi.egd')
        self.assertEqual(state(exam['extent']), ('verified', 'stated', []))

    def test_a_reach_with_no_landmark_is_absent_and_never_attached(self):
        value = answer()
        value['encounter']['reach'][0]['landmark'] = 'not_stated'
        inventory = run(value)
        self.assertIsNone(ev(inventory, 'E0')['extent'])
        self.assertEqual(inventory.encounter_facts['reach'][0]['state'], 'absent')


class Visits(SimpleTestCase):
    LINES = {'P1': 'Office visit. Total time spent: 45 minutes.', 'P2': 'Medical decision making: moderate.',
             'P3': 'The visit was not separately identifiable from the procedure.'}
    TEXT = doc(*LINES.values())

    def run_visit(self, facts, kind='em_visit'):
        visit = event('E1', procedure=attr('office_em'), kind=attr(kind, 'Office visit', ['P1']),
                      technique=attr('not_stated'), target=target(), status=attr('performed', 'Office visit', ['P1']),
                      purpose=attr('not_stated'))
        value = answer(self.LINES, lesions=[], events=[visit], encounter=encounter(
            date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []},
            documenting_endoscopist={'words': '', 'passages': []}, team=[], reach=[], visit_facts=facts))
        return run(value, self.TEXT)

    def facts(self, basis, separate, event_id='E1'):
        return {'event': event_id, 'basis': basis, 'separately_identifiable': separate}

    def test_visit_facts_attach_to_the_visit_and_are_checked(self):
        inventory = self.run_visit([self.facts(attr('total_time', 'Total time spent: 45 minutes', ['P1']),
                                               attr('denied', 'not separately identifiable', ['P3']))])
        visit = ev(inventory, 'E1')['visit']
        self.assertEqual(state(visit['basis']), ('verified', 'stated', []))
        self.assertEqual(visit['basis']['literals'], {'minutes': [45]})
        self.assertEqual(state(visit['separately_identifiable']), ('verified', 'stated', []))
        self.assertEqual(inventory.encounter_facts['visits'], [
            {'event': 'E1', 'basis': 'total_time', 'basis_state': 'verified', 'separately_identifiable': 'denied',
             'separately_identifiable_state': 'verified', 'attached': True}])

    def test_each_visit_check_fails_on_its_own_words(self):
        cases = ((attr('total_time', 'Office visit', ['P1']), 'duration_missing'),
                 (attr('medical_decision_making', 'moderate', ['P2']), 'label_missing'))
        for basis, reason in cases:
            visit = ev(self.run_visit([self.facts(basis, attr('not_stated'))]), 'E1')['visit']
            with self.subTest(reason):
                self.assertEqual(visit['basis']['reasons'], [reason])
        visit = ev(self.run_visit([self.facts(attr('medical_decision_making', 'Medical decision making', ['P2']),
                                              attr('denied', 'from the procedure', ['P3']))]), 'E1')['visit']
        self.assertEqual(state(visit['basis']), ('verified', 'stated', []))
        self.assertEqual(visit['separately_identifiable']['reasons'], ['negation_missing'])

    def test_visit_facts_on_another_kind_or_an_unknown_event_are_discarded(self):
        for kind, event_id in (('examination', 'E1'), ('em_visit', MODEL_TEXT[:20])):
            facts = [self.facts(attr('total_time', 'Total time spent: 45 minutes', ['P1']), attr('not_stated'),
                                event_id=event_id)]
            inventory = self.run_visit(facts, kind=kind)
            with self.subTest(kind=kind):
                self.assertIsNone(ev(inventory, 'E1')['visit'])
                self.assertIn({'where': 'encounter.visit_facts[0]', 'reason': 'visit_not_permitted'},
                              inventory.verification['discarded'])
                self.assertEqual(inventory.verification['reasons'].get('visit_not_permitted'), 1)

    def test_a_second_set_of_visit_facts_is_not_attached(self):
        first = self.facts(attr('total_time', 'Total time spent: 45 minutes', ['P1']), attr('not_stated'))
        second = self.facts(attr('medical_decision_making', 'Medical decision making', ['P2']), attr('not_stated'))
        inventory = self.run_visit([first, second])
        self.assertEqual(ev(inventory, 'E1')['visit']['basis']['value'], 'total_time')
        self.assertEqual([item['attached'] for item in inventory.encounter_facts['visits']], [True, False])


class Lesions(SimpleTestCase):
    def test_a_verified_lesion(self):
        record = les(run(answer()), 'L1')
        self.assertEqual((record['state'], record['reasons']), ('verified', []))
        self.assertEqual(record['words']['text'], '7 mm sessile polyp')
        self.assertEqual(record['size'], {'mm': [7], 'span': {'start': TEXT.index('7 mm'), 'end': TEXT.index('7 mm') + 4,
                                                             'text': '7 mm', 'match': 'exact', 'occurrences': 1}})
        self.assertEqual(state(record['site']), ('verified', 'stated', []))
        self.assertEqual((record['distinct_from'], record['possibly_same_as']), ([], []))

    def test_each_failure(self):
        cases = ((dict(words='7 mm sessile polyp in the rectum'), ['words_unlocated']),
                 (dict(words=''), ['words_missing']),
                 (dict(size_words='small'), ['words_unlocated']),
                 (dict(size_words='sessile'), ['size_missing']),
                 (dict(site_words='polyp', landmark='cecum'), ['landmark_missing']),
                 (dict(site_words='transverse colon', landmark='rectum'), ['landmark_conflict']))
        for changes, reasons in cases:
            record = les(run(answer(lesions=[lesion(**changes)])), 'L1')
            with self.subTest(changes):
                self.assertEqual((record['state'], record['reasons']), ('unverified', reasons))

    def test_site_and_size_count_only_where_given(self):
        record = les(run(answer(lesions=[lesion(site_words='', size_words='')])), 'L1')
        self.assertEqual((record['state'], record['reasons']), ('verified', []))
        self.assertEqual(state(record['site']), ('unverified', 'absent', ['words_missing']),
                         'the landmark itself is not bound, and no passage is read for it (EB1)')
        self.assertEqual(record['size'], {'mm': [], 'span': None})

    def test_distances_in_site_words_are_recorded_for_distinctness(self):
        lines = dict(LINES, P2='A 7 mm sessile polyp in the sigmoid colon at 30 cm was removed with a cold snare.')
        text = TEXT.replace(LINES['P2'], lines['P2'])
        value = answer(lines, lesions=[lesion(landmark='sigmoid_colon', site_words='sigmoid colon at 30 cm')],
                       events=[examination(), event(target=target('L1', 'sigmoid_colon', 'sigmoid colon at 30 cm',
                                                                  ['P2'])), denial()])
        inventory = run(value, text)
        self.assertEqual(les(inventory, 'L1')['site']['literals'], {'landmarks': ['sigmoid_colon'],
                                                                   'distances_cm': [30]})
        self.assertEqual(ev(inventory, 'E1')['target']['literals'], {'landmarks': ['sigmoid_colon'],
                                                                    'distances_cm': [30]})


class DateOfService(SimpleTestCase):
    def run_date(self, date_of_service, lines=None, text=None):
        lines = lines or {'P1': 'Date of service: 03/14/2026. DOB: 01/02/1960.', 'P2': 'Signed 03/15/2026.'}
        value = answer(lines, lesions=[], events=[], encounter=encounter(
            date_of_service=date_of_service, documenting_endoscopist={'words': '', 'passages': []}, team=[], reach=[]))
        return run(value, text or doc(*lines.values()))

    def test_a_stated_verified_date_with_its_other_dates_by_role(self):
        facts = self.run_date({'value': '2026-03-14', 'state': 'stated', 'words': '03/14/2026', 'passages': ['P1'],
                               'other_dates': [
                                   {'value': '1960-01-02', 'role': 'birth', 'words': '01/02/1960', 'passages': ['P1']},
                                   {'value': '2026-03-15', 'role': 'report_time', 'words': '03/15/2026',
                                    'passages': ['P2']},
                                   {'value': '2026-03-16', 'role': 'other_document', 'words': '03/15/2026',
                                    'passages': ['P2']}]}).encounter_facts['date_of_service']
        self.assertEqual((facts['state'], facts['value'], facts['verified'], facts['reasons']),
                         ('stated', '2026-03-14', True, []))
        self.assertEqual(facts['others']['birth'][0]['verified'], True)
        self.assertEqual(facts['others']['report_time'][0]['verified'], True)
        self.assertEqual((facts['others']['other_document'][0]['verified'],
                          facts['others']['other_document'][0]['reasons']), (False, ['date_mismatch']))
        self.assertEqual(facts['readings'], ['2026-03-14'], 'the date of birth in its passage is never a reading')

    def test_a_stated_date_that_its_words_do_not_bear_out(self):
        for words in ('03/15/2026', 'Date of service: 03/14/2026. DOB: 01/02/1960'):
            facts = self.run_date({'value': '2026-03-14', 'state': 'stated', 'words': words, 'passages': ['P1', 'P2'],
                                   'other_dates': []}).encounter_facts['date_of_service']
            with self.subTest(words):
                self.assertEqual((facts['value'], facts['verified'], facts['reasons']), (None, False, ['date_mismatch']))
        self.assertEqual(facts['readings'], ['1960-01-02', '2026-03-14', '2026-03-15'],
                         'with no role given to it, a date in its passages stays a reading')

    def test_several_dates_of_service(self):
        facts = self.run_date({'value': '', 'state': 'several', 'words': '', 'passages': [], 'other_dates': [
            {'value': '2026-03-14', 'role': 'this_encounter', 'words': '03/14/2026', 'passages': ['P1']},
            {'value': '2026-03-15', 'role': 'this_encounter', 'words': '03/15/2026', 'passages': ['P2']},
            {'value': '2026-03-17', 'role': 'this_encounter', 'words': '03/14/2026', 'passages': ['P1']}]})
        record = facts.encounter_facts['date_of_service']
        self.assertEqual((record['value'], record['verified'], record['candidates']),
                         (None, False, ['2026-03-14', '2026-03-15']))
        self.assertIsNone(facts.encounter_facts['date_of_service']['value'])

    def test_a_stated_date_beside_another_date_for_this_encounter(self):
        inventory = self.run_date({'value': '2026-03-14', 'state': 'stated', 'words': '03/14/2026', 'passages': ['P1'],
                                   'other_dates': [{'value': '2026-03-15', 'role': 'this_encounter',
                                                    'words': '03/15/2026', 'passages': ['P2']}]})
        record = inventory.encounter_facts['date_of_service']
        self.assertEqual((record['value'], record['verified'], record['reasons']), (None, False, ['date_mismatch']))

    def test_not_stated_and_a_stated_date_with_no_value(self):
        record = self.run_date({'value': '', 'state': 'not_stated', 'words': '', 'passages': [],
                                'other_dates': []}).encounter_facts['date_of_service']
        self.assertEqual((record['state'], record['value'], record['verified'], record['readings']),
                         ('not_stated', None, False, []))
        record = self.run_date({'value': '', 'state': 'stated', 'words': '03/14/2026', 'passages': ['P1'],
                                'other_dates': []}).encounter_facts['date_of_service']
        self.assertEqual((record['verified'], record['reasons']), (False, ['date_mismatch']))

    def test_an_opened_date_is_no_service_date(self):
        value = answer(open_questions=[{'about': 'date_of_service', 'events': [], 'lesions': [], 'passages': ['P1']}],
                       events=[examination(), event(time=attr('earlier_encounter', 'in 2024', ['P2'])), denial()])
        value['passages'][1]['text'] = LINES['P2']
        inventory = run(value)
        record = inventory.encounter_facts['date_of_service']
        self.assertEqual((record['value'], record['verified'], record['reasons']), (None, False, []))
        self.assertEqual(inventory.open_questions[0]['attached_to'], [{'encounter': 'date_of_service'}])
        self.assertEqual(inventory.verification['counts']['date_of_service']['open'], 1)


class Time(SimpleTestCase):
    LINES = dict(LINES, P7='A prior colonoscopy in 2024 removed a polyp.')
    TEXT = TEXT + 'A prior colonoscopy in 2024 removed a polyp.\n'

    def earlier(self, words='in 2024'):
        prior = event('E3', kind=attr('snare', 'removed', ['P7']), technique=attr('not_stated'), target=target(),
                      time=attr('earlier_encounter', words, ['P7']), status=attr('performed', 'removed', ['P7']),
                      purpose=attr('not_stated'))
        return run(answer(self.LINES, events=[examination(), event(), denial(), prior]), self.TEXT)

    def test_an_earlier_time_verified_by_its_date_literal(self):
        record = ev(self.earlier(), 'E3')
        self.assertEqual(state(record['time']), ('verified', 'stated', []))
        self.assertEqual(record['current'], 'no')
        self.assertEqual(verify.exclusion_basis('time', record['time']), 'literal')

    def test_time_state_rejudges_it_against_a_members_date_with_no_text_read(self):
        record = ev(self.earlier(), 'E3')['time']
        self.assertEqual(verify.time_state(record, date(2023, 6, 1))['reasons'], ['date_mismatch'])
        self.assertEqual(verify.time_state(record, '2026-11-09')['state'], 'verified')

    def test_a_marker_without_a_date(self):
        self.assertEqual(state(ev(self.earlier('A prior colonoscopy'), 'E3')['time']), ('verified', 'stated', []))
        self.assertEqual(ev(self.earlier('colonoscopy'), 'E3')['time']['reasons'], ['time_marker_missing'])


class OpenQuestions(SimpleTestCase):
    def test_attachment_and_open_attributes(self):
        questions = [{'about': 'technique', 'events': ['E1', 'E9'], 'lesions': ['L1', 'L9'], 'passages': ['P2', 'P9']},
                     {'about': 'contradiction', 'events': ['E1'], 'lesions': [], 'passages': []},
                     {'about': 'identity', 'events': ['E1'], 'lesions': [], 'passages': []},
                     {'about': 'extent', 'events': ['E0', 'E1'], 'lesions': [], 'passages': []},
                     {'about': 'completion', 'events': ['E0'], 'lesions': [], 'passages': []},
                     {'about': 'visit_basis', 'events': ['E1'], 'lesions': [], 'passages': []},
                     {'about': 'other', 'events': ['E1'], 'lesions': [], 'passages': []}]
        draft_seen = []
        with mock.patch.object(normalize, 'LINKED_STEPS', ()):
            draft = normalize.Draft(accepted(answer(open_questions=questions)), TEXT)
            draft.build()
            draft_seen.append(draft.identity_open)
            inventory = draft.finish()
        snare, exam = ev(inventory, 'E1'), ev(inventory, 'E0')
        self.assertTrue(snare['technique']['open'] and snare['status']['open'])
        self.assertTrue(exam['extent']['open'] and exam['completion']['open'])
        self.assertFalse(snare['kind']['open'] or snare['time']['open'])
        self.assertEqual(draft_seen, [frozenset({'E1'})])
        stored = inventory.open_questions
        self.assertEqual(stored[0], {'about': 'technique', 'events': ['E1'], 'lesions': ['L1'], 'passages': ['P2'],
                                     'attached_to': [{'event': 'E1', 'attribute': 'technique'}]})
        self.assertEqual(stored[1]['attached_to'], [{'event': 'E1', 'attribute': 'status'}])
        self.assertEqual(stored[2]['attached_to'], [{'event': 'E1', 'attribute': 'identity'}])
        self.assertEqual(stored[3]['attached_to'], [{'event': 'E0', 'attribute': 'extent'}])
        self.assertEqual(stored[4]['attached_to'], [{'event': 'E0', 'attribute': 'completion'}])
        self.assertEqual(stored[5]['attached_to'], [], 'E1 has no visit')
        self.assertEqual(stored[6]['attached_to'], [])
        self.assertIn('open_questions[0] names 3 ids the answer does not define.', inventory.verification['problems'])
        self.assertEqual(inventory.verification['counts']['technique']['open'], 1)
        self.assertFalse(verify.usable(snare['technique']))


class Derived(SimpleTestCase):
    def test_current_families_and_procedure_day(self):
        inventory = run(answer())
        self.assertEqual(inventory.encounter_facts['derived'], {
            'current_families': ['gi.colonoscopy'], 'procedure_day': {'performed': ['gi.colonoscopy'], 'possible': []},
            'absent': []})

    def test_an_unusable_current_act_makes_its_family_possible(self):
        value = answer(events=[event('E1', status=attr('performed', 'excised', ['P2']))])
        inventory = run(value)
        self.assertEqual(inventory.encounter_facts['derived']['procedure_day'],
                         {'performed': [], 'possible': ['gi.colonoscopy']})
        self.assertEqual(inventory.encounter_facts['derived']['current_families'], [])

    def test_absent_structures(self):
        lines = dict(LINES, P7='Status post total colectomy; the colon is surgically absent.')
        value = answer(lines)
        value['encounter']['anatomy'] = [
            {'state': 'absent', 'landmark': 'colon', 'words': 'the colon is surgically absent', 'passages': ['P7']},
            {'state': 'absent', 'landmark': 'rectum', 'words': 'the colon', 'passages': ['P7']},
            {'state': 'altered', 'landmark': 'not_stated', 'words': '', 'passages': []}]
        inventory = run(value, TEXT + lines['P7'] + '\n')
        anatomy = inventory.encounter_facts['anatomy']
        self.assertEqual([(item['anatomy'], item['state'], item['reasons']) for item in anatomy],
                         [('absent', 'verified', []), ('absent', 'unverified', ['landmark_conflict']),
                          ('altered', 'absent', [])])
        self.assertEqual(inventory.encounter_facts['derived']['absent'], ['colon'])


class NoMergeOrDrop(SimpleTestCase):
    def test_every_event_and_lesion_stays_in_order_with_its_id(self):
        broken = {name: attr(value, f'{MODEL_TEXT} words', ['P9'])
                  for name, value in (('procedure', 'egd'), ('kind', 'biopsy'), ('technique', 'forceps'),
                                      ('time', 'future'), ('performer', 'other_clinician'), ('status', 'planned'),
                                      ('purpose', 'diagnostic'))}
        events = [event('E5', **broken, target=target('L9', 'cecum', 'x', ['P9'])), examination('E0'), event('E1'),
                  event('E1b'), denial('E2'), event('E1c')]
        lesions = [lesion('L2', words=MODEL_TEXT, passages=['P9']), lesion('L1'), lesion('L3')]
        inventory = run(answer(events=events, lesions=lesions))
        self.assertEqual([item['id'] for item in inventory.events['events']], ['E5', 'E0', 'E1', 'E1b', 'E2', 'E1c'])
        self.assertEqual([item['id'] for item in inventory.events['lesions']], ['L2', 'L1', 'L3'])
        broken_record = ev(inventory, 'E5')
        for name in broken:
            with self.subTest(name):
                self.assertEqual(broken_record[name]['state'], 'unverified')
        self.assertEqual(ev(inventory, 'E1'), {**ev(inventory, 'E1b'), 'id': 'E1'},
                         'two events stating one act stay two events')


class NoModelText(SimpleTestCase):
    def test_no_model_written_string_is_stored(self):
        unknown = MODEL_TEXT[:24]
        lines = dict(LINES, P7=f'{MODEL_TEXT} quoted nowhere')
        value = answer(lines, events=[
            examination(), event(target=target(unknown, 'transverse_colon', MODEL_TEXT, ['P2', unknown]),
                                 part_of=unknown, contradicts=[{'event': unknown, 'passages': [unknown]}],
                                 kind=attr('snare', MODEL_TEXT, ['P7'])),
            denial(scope=scope('listed_targets', MODEL_TEXT, ['P3'], [unknown, 'L1']))],
            open_questions=[{'about': 'status', 'events': [unknown], 'lesions': [unknown], 'passages': [unknown]}])
        value['encounter']['reach'][0]['event'] = unknown
        value['encounter']['visit_facts'] = [{'event': unknown, 'basis': attr('total_time', MODEL_TEXT, [unknown]),
                                             'separately_identifiable': attr('not_stated')}]
        inventory = run(value)
        dumped = json.dumps([inventory.events, inventory.encounter_facts, inventory.open_questions,
                             inventory.verification])
        self.assertNotIn(MODEL_TEXT[:20], dumped)


class Stability(SimpleTestCase):
    def test_the_same_answer_and_text_give_the_same_inventory_and_sha256(self):
        first, second = run(answer()), run(answer())
        self.assertEqual(first, second)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(json.loads(json.dumps(first.content())), first.content())
        self.assertEqual(first.text_sha256, hashlib.sha256(TEXT.encode('utf-8')).hexdigest())

    def test_any_change_changes_the_sha256(self):
        base = run(answer()).sha256
        changed = answer(events=[examination(), event(technique=attr('cold_snare', 'COLD snare', ['P2'])), denial()])
        self.assertNotEqual(run(changed).sha256, base)
        self.assertNotEqual(run(answer(), TEXT + '\n').sha256, base)

    def test_normalization_is_db_free_under_run_bounded(self):
        # SimpleTestCase refuses every database query, in the forked child as here; the child's result is the same.
        with mock.patch.object(normalize, 'LINKED_STEPS', ()):
            parsed = accepted(answer())
            bounded_result = bounded.run_bounded(normalize.normalize, parsed, TEXT, seconds=60,
                                                 memory_bytes=512 * 1024 * 1024)
            direct = normalize.normalize(parsed, TEXT)
        self.assertEqual(bounded_result, direct)
        self.assertEqual(bounded_result.sha256, direct.sha256)

    def test_the_stored_row_reads_back_equal(self):
        inventory = run(answer())
        fields = store.row(encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN, revision_text=TEXT,
                           text_sha256=inventory.text_sha256, request_sha256='2' * 64, response_sha256='3' * 64,
                           **inventory.content())
        loaded = store.load(json.loads(json.dumps(fields)), text_sha256=inventory.text_sha256,
                            response_sha256='3' * 64)
        self.assertEqual(loaded.events, inventory.events)
        self.assertEqual(loaded.encounter_facts, inventory.encounter_facts)
        self.assertEqual(loaded.open_questions, inventory.open_questions)
        self.assertEqual(loaded.verification['counts'], inventory.verification['counts'])
        self.assertEqual(loaded.label, LABEL)

    def test_only_an_accepted_answer_is_normalized(self):
        with self.assertRaises(TypeError):
            normalize.normalize(read.refuse('json', 'there is no answer text'), TEXT)
        with self.assertRaises(TypeError):
            normalize.normalize(accepted(answer()), b'bytes')


class LinkedSteps(SimpleTestCase):
    def test_the_steps_are_slice_s03s_in_the_contracts_order(self):
        self.assertEqual(normalize.LINKED_STEPS, (('studio.interpretation.identity', 'distinguish'),
                                                  ('studio.interpretation.identity', 'link'),
                                                  ('studio.interpretation.relations', 'relate'),
                                                  ('studio.interpretation.mapping', 'map_events')))

    def test_each_step_is_called_in_order_with_the_draft_and_its_changes_are_kept(self):
        CALLS.clear()
        inventory = run(answer(), steps=[('tests.test_interpretation_normalize', 'spy_one'),
                                         ('tests.test_interpretation_normalize', 'spy_two')])
        self.assertEqual(CALLS, [('one', ['E0', 'E1', 'E2'], ['L1'], date(2026, 3, 14)), ('two', 0)])
        self.assertEqual(inventory.events['relations'][-1], {
            'id': 'R1', 'type': 'independent', 'statement': 'E2', 'event': 'E1', 'attribute': 'scope',
            'reason': 'exceptive', 'claimed_by_model': False, 'passages': ['P3']})
        self.assertEqual(ev(inventory, 'E1')['catalogue_kind'], 'snare')
        self.assertEqual(ev(inventory, 'E1')['target']['identity'], 'verified')
        self.assertEqual(inventory.verification['relations'], {'independent': 1})

    def test_a_missing_step_raises_and_nothing_is_skipped(self):
        with self.assertRaises(ModuleNotFoundError):
            run(answer(), steps=[('studio.interpretation.no_such_module_s02', 'link')])
        with self.assertRaises(AttributeError):
            run(answer(), steps=[('tests.test_interpretation_normalize', 'no_such_step')])

    def test_a_step_giving_a_reason_outside_the_closed_lists_fails_loudly(self):
        with self.assertRaises(ValueError):
            run(answer(), steps=[('tests.test_interpretation_normalize', 'spy_bad_reason')])

    def test_passages_of(self):
        with mock.patch.object(normalize, 'LINKED_STEPS', ()):
            draft = normalize.Draft(accepted(answer()), TEXT)
            draft.build()
        start = TEXT.index('cold snare')
        self.assertEqual(draft.passages_of({'start': start, 'end': start + 10}), ['P2'])
        self.assertEqual(draft.passages_of({'start': 0, 'end': len(TEXT)}), [])


class Report(SimpleTestCase):
    def test_the_report_counts_and_names_by_place(self):
        report = run(answer()).verification
        self.assertEqual(set(report), {'label', 'counts', 'reasons', 'relations', 'discarded', 'problems', 'refused'})
        self.assertEqual((report['label'], report['refused'], report['reasons'], report['relations'],
                          report['discarded'], report['problems']), (LABEL, False, {}, {}, [], []))
        self.assertEqual(report['counts']['time'], {'claimed': 3, 'verified': 3, 'unverified': 0, 'absent': 0,
                                                    'discarded': 0, 'open': 0})
        self.assertEqual(report['counts']['reach'], {'claimed': 1, 'verified': 1, 'unverified': 0, 'absent': 0,
                                                     'discarded': 0, 'open': 0})
        self.assertEqual(report['counts']['team']['verified'], 1)
        self.assertTrue(set(report['counts']) <= set(normalize.COUNTED))


def every_reason_scenario() -> list:
    """One answer per closed-list reason of verify.REASONS (and the text it is read against)."""
    scenarios = []

    def add(reason, value, text=TEXT):
        scenarios.append((reason, value, text))

    e = lambda **changes: answer(events=[examination(), event(**changes), denial()])  # noqa: E731
    add('passage_unknown', e(kind=attr('snare', 'removed', ['P9'])))
    add('passage_unlocated', answer(dict(LINES, P7='nowhere at all in it'),
                                    events=[examination(), event(kind=attr('snare', 'removed', ['P7'])), denial()]))
    add('words_missing', e(kind=attr('snare', '', ['P2'])))
    add('words_unlocated', e(kind=attr('snare', 'excised', ['P2'])))
    add('date_mismatch', answer(encounter=encounter(date_of_service={
        'value': '2026-03-15', 'state': 'stated', 'words': '03/14/2026', 'passages': ['P1'], 'other_dates': []})))
    add('date_unchecked', answer(encounter=encounter(date_of_service={
        'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []}),
        events=[examination(), event(time=attr('earlier_encounter', '03/14/2026', ['P1'])), denial()]))
    add('name_mismatch', answer(encounter=encounter(team=[]), events=[
        examination(), event(performer=attr('documenting_team', 'Robin Synthetic', ['P6'])), denial()]))
    add('name_not_other', e(performer=attr('other_clinician', 'Grace Okafor', ['P4'])))
    add('size_missing', answer(lesions=[lesion(size_words='sessile')]))
    add('landmark_missing', e(target=target('L1', 'cecum', 'A 7 mm sessile polyp', ['P2'])))
    add('landmark_conflict', e(target=target('L1', 'cecum', 'transverse colon', ['P2'])))
    add('device_reach', answer(dict(LINES, P5='The guidewire was advanced to the cecum.'),
                               encounter=encounter(reach=[{'event': 'E0', 'landmark': 'cecum',
                                                           'words': 'guidewire was advanced to the cecum',
                                                           'passages': ['P5'], 'completion': attr('not_stated')}]),
                               events=[examination(technique=attr('endoscope', 'colonoscopy', ['P1']),
                                                   kind=attr('examination', 'colonoscopy', ['P1']),
                                                   status=attr('performed', 'advanced to the cecum', ['P5'])),
                                       event(), denial()]),
        TEXT.replace(LINES['P5'], 'The guidewire was advanced to the cecum.'))
    add('device_missing', e(technique=attr('hot_snare', 'cold snare', ['P2'])))
    two = {'P1': 'EGD: the esophagus was normal.', 'P2': 'Colonoscopy: a polyp was removed with a cold snare.'}
    two_text = doc(*two.values())
    no_facts = encounter(date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [],
                                          'other_dates': []}, documenting_endoscopist={'words': '', 'passages': []},
                         team=[], reach=[])
    exams = [event('E0', procedure=attr('egd', 'EGD', ['P1']), kind=attr('examination', 'EGD', ['P1']),
                   technique=attr('not_stated'), target=target(), status=attr('performed', 'normal', ['P1']),
                   purpose=attr('not_stated')),
             event('E1', procedure=attr('colonoscopy', 'Colonoscopy', ['P2']),
                   kind=attr('examination', 'Colonoscopy', ['P2']), technique=attr('not_stated'), target=target(),
                   status=attr('performed', 'removed', ['P2']), purpose=attr('not_stated'))]
    add('procedure_name_missing', answer(two, lesions=[], encounter=no_facts, events=exams + [
        event('E2', procedure=attr('egd', 'Colonoscopy', ['P2']), kind=attr('snare', 'removed', ['P2']),
              technique=attr('not_stated'), target=target(), status=attr('performed', 'removed', ['P2']),
              purpose=attr('not_stated'))]), two_text)
    add('procedure_unsettled', answer(two, lesions=[], encounter=no_facts, events=exams + [
        event('E2', kind=attr('snare', 'removed', ['P2']), technique=attr('not_stated'), target=target(),
              status=attr('performed', 'removed', ['P2']), purpose=attr('not_stated'))]), two_text)
    add('negation_missing', answer(events=[examination(), event(), denial(
        status=attr('not_performed', 'polyp was removed', ['P3']))]))
    add('quantifier_missing', answer(events=[examination(), event(), denial(
        scope=scope('all_of_kind', 'polyp was removed', ['P3']))]))
    visit_lines = {'P1': 'Office visit. Total time spent: 45 minutes.', 'P2': 'Medical decision making: moderate.',
                   'P3': 'The visit was not separately identifiable from the procedure.'}
    visit = event('E1', procedure=attr('office_em'), kind=attr('em_visit', 'Office visit', ['P1']),
                  technique=attr('not_stated'), target=target(), status=attr('performed', 'Office visit', ['P1']),
                  purpose=attr('not_stated'))

    def visit_answer(basis, separate, kind='em_visit'):
        facts = encounter(date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [],
                                           'other_dates': []}, documenting_endoscopist={'words': '', 'passages': []},
                          team=[], reach=[],
                          visit_facts=[{'event': 'E1', 'basis': basis, 'separately_identifiable': separate}])
        return answer(visit_lines, lesions=[], encounter=facts,
                      events=[dict(visit, kind=attr(kind, 'Office visit', ['P1']))])
    visit_text = doc(*visit_lines.values())
    add('duration_missing', visit_answer(attr('total_time', 'Office visit', ['P1']), attr('not_stated')), visit_text)
    add('label_missing', visit_answer(attr('medical_decision_making', 'moderate', ['P2']), attr('not_stated')),
        visit_text)
    add('planning_missing', e(status=attr('planned', 'was removed', ['P2'])))
    add('failure_missing', e(status=attr('attempted_not_completed', 'was removed', ['P2'])))
    add('time_marker_missing', e(time=attr('earlier_encounter', 'removed', ['P2'])))
    add('other_occasion', e(time=attr('current_encounter', 'at the original procedure', ['P2'])))  # D35, unlocated
    add('current_unanchored', e(time=attr('current_encounter', 'sessile polyp', ['P2'])))  # D54: not a whole frame
    add('facility_marker_missing', e(performer=attr('other_facility', 'sessile polyp', ['P2'])))
    add('scope_target_mismatch', answer(events=[examination(), event(), denial(
        scope=scope('single_target', 'No other', ['P3']))]))
    add('umbrella_on_positive', e(kind=attr('intervention', 'removed', ['P2'])))
    add('inconsistent_status_time', e(time=attr('future', 'removed', ['P2'])))
    add('part_of_invalid', e(part_of='E1'))
    add('claim_unknown_event', e(contradicts=[{'event': 'E77', 'passages': []}]))
    add('lesion_unknown', e(target=target('L7', 'transverse_colon', 'transverse colon', ['P2'])))
    add('reach_not_permitted', answer(events=[examination(time=attr('future', 'advanced', ['P5'])), event(), denial()]))
    biopsy = 'Biopsies of the ascending colon were taken.'
    add('reach_inferred', answer(dict(LINES, P7=biopsy), encounter=encounter(reach=[{
        'event': 'E0', 'landmark': 'ascending_colon', 'words': 'ascending colon', 'passages': ['P7'],
        'completion': attr('not_stated')}]), events=[examination(), event(), denial(), event(
            'E3', kind=attr('biopsy', 'Biopsies', ['P7']), technique=attr('not_stated'),
            target=target('', 'ascending_colon', 'ascending colon', ['P7']),
            status=attr('performed', 'were taken', ['P7']), purpose=attr('not_stated'))]), TEXT + biopsy + '\n')
    add('visit_not_permitted', visit_answer(attr('total_time', 'Total time spent: 45 minutes', ['P1']),
                                            attr('not_stated'), kind='examination'), visit_text)
    add('scope_not_permitted', e(scope=scope('single_target', 'sessile polyp', ['P2'])))
    return scenarios


class EveryReason(SimpleTestCase):
    def test_every_closed_list_reason_is_reached_by_its_own_scenario(self):
        reached = set()
        for reason, value, text in every_reason_scenario():
            report = run(value, text).verification
            with self.subTest(reason):
                self.assertIn(reason, report['reasons'])
            reached.update(report['reasons'])
        self.assertEqual({reason for reason, _, _ in every_reason_scenario()}, set(verify.REASONS))
        self.assertTrue(set(verify.REASONS) <= reached)
        self.assertFalse(reached & set(verify.REMOVED_REASONS))


class SlipV5(SimpleTestCase):
    """The trial's v5 slip (contract 7, S4): strings cut before a closing parenthesis still bind; names compare by
    parenthetical-free tokens, so a cut name never makes another performer."""

    def test_cut_strings_bind_and_compare_equal(self):
        lines = dict(LINES, P4='Endoscopist: Grace Okafor, MD (fictional')
        value = answer(lines, events=[examination(), event(performer=attr('documenting_team',
                                                                          'Grace Okafor, MD (fictional', ['P4'])),
                                      denial()])
        value['encounter']['documenting_endoscopist']['words'] = 'Grace Okafor, MD (fictional'
        inventory = run(value)
        self.assertEqual(passage(inventory, 'P4')['extended'], 'closing_bracket')
        self.assertEqual(inventory.encounter_facts['documenting_endoscopist']['names'],
                         [{'tokens': ['grace', 'okafor'], 'titled': False, 'credentialed': True}])
        performer = ev(inventory, 'E1')['performer']
        self.assertEqual(state(performer), ('verified', 'stated', []))
        self.assertNotIn('name_mismatch', json.dumps(inventory.verification))


if __name__ == '__main__':  # pragma: no cover
    sys.exit('Run with manage.py test.')
