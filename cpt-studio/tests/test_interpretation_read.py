"""The strict reader of one Gemini answer (Gemini migration slice S01; design/contract.md 3.3 and 4.5), TEXT-ONLY: every
refusal row - strict JSON, the schema, the bounds, the ids, the ISO dates - in its order, each bound at its limit (read)
and one past it (refused, named by count, never truncated); the item-level findings that never refuse the answer; the
adjudicated values (an exceptive scope, the colon regions) read; no refusal repeating the model's text; and the pin
check on LOCAL_SCHEMA. Synthetic answers built in code; nothing is sent."""
from __future__ import annotations

import copy
import json
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation import read, schema
from studio.types import to_jsonable

REFUSED = 'The interpretation was not used: '
MODEL_TEXT = 'SYNTHETIC-MODEL-TEXT-0001'  # model-written wording planted in a refused answer: never repeated
ATTRIBUTES = ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose')
P2 = 'A 7 mm sessile polyp in the transverse colon was removed with a cold snare.'


def attribute(value: str, words: str = '', passages=()) -> dict:
    return {'value': value, 'words': words, 'passages': list(passages)}


def event(id: str = 'E1', **changes) -> dict:
    """A performed cold snare removal of L1 (a synthetic, schema-valid event)."""
    item = {
        'id': id,
        'procedure': attribute('colonoscopy', 'colonoscopy', ['P1']),
        'kind': attribute('snare', 'removed', ['P2']),
        'technique': attribute('cold_snare', 'cold snare', ['P2']),
        'target': {'lesion': 'L1', 'landmark': 'transverse_colon', 'words': 'A 7 mm sessile polyp', 'passages': ['P2']},
        'time': attribute('current_encounter'),
        'performer': attribute('documenting_team'),
        'status': attribute('performed', 'was removed with a cold snare', ['P2']),
        'scope': {'value': 'not_applicable', 'targets': [], 'words': '', 'passages': []},
        'purpose': attribute('removal', 'removed', ['P2']),
        'part_of': '',
        'sequence': 0,
        'contradicts': [],
    }
    item.update(changes)
    return item


def bare_event(id: str) -> dict:
    """An event that cites no passage at all."""
    item = event(id)
    for name in ATTRIBUTES:
        item[name] = dict(item[name], passages=[])
    return item


def lesion(id: str = 'L1', **changes) -> dict:
    item = {'id': id, 'words': '7 mm sessile polyp', 'landmark': 'transverse_colon', 'site_words': 'transverse colon',
            'size_words': '7 mm', 'multiplicity': 'single', 'passages': ['P2']}
    item.update(changes)
    return item


def answer(**changes) -> dict:
    """A synthetic, schema-valid answer: a colonoscopy with one polyp removed, and an exceptive denial."""
    value = {
        'passages': [{'id': 'P1', 'text': 'Synthetic colonoscopy note. Date of service: 03/14/2026.'},
                     {'id': 'P2', 'text': P2},
                     {'id': 'P3', 'text': 'No other polyp was removed.'}],
        'encounter': {
            'date_of_service': {'value': '2026-03-14', 'state': 'stated', 'words': '03/14/2026', 'passages': ['P1'],
                                'other_dates': []},
            'documenting_endoscopist': {'words': '', 'passages': []},
            'team': [],
            'anatomy': [],
            'reach': [{'event': 'E0', 'landmark': 'cecum', 'words': '', 'passages': [],
                       'completion': attribute('not_stated')}],
            'visit_facts': [],
        },
        'lesions': [lesion()],
        'events': [
            event('E0', kind=attribute('examination', 'colonoscopy', ['P1']), technique=attribute('endoscope'),
                  target={'lesion': '', 'landmark': 'not_stated', 'words': '', 'passages': []},
                  status=attribute('performed'), purpose=attribute('diagnostic'), sequence=1),
            event('E1', sequence=2),
            event('E2', kind=attribute('removal', 'removed', ['P3']), technique=attribute('not_stated'),
                  target={'lesion': '', 'landmark': 'not_stated', 'words': '', 'passages': []},
                  status=attribute('not_performed', 'No other polyp was removed', ['P3']),
                  scope={'value': 'exceptive', 'targets': [], 'words': 'No other', 'passages': ['P3']},
                  purpose=attribute('not_stated')),
        ],
        'open_questions': [],
    }
    value.update(changes)
    return value


def text(value) -> str:
    return json.dumps(value)


def cited(value: dict) -> int:
    """The passage ids an answer cites: every ``passages`` list but the passage table itself."""
    count, pending = 0, [value[key] for key in ('encounter', 'lesions', 'events', 'open_questions')]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            for key, item in node.items():
                if key == 'passages':
                    count += len(item)
                else:
                    pending.append(item)
        elif isinstance(node, list):
            pending.extend(node)
    return count


def with_cited(total: int) -> dict:
    """answer() with events added so that it cites exactly ``total`` passage ids (each list at most 8)."""
    value = answer()
    need, added = total - cited(value), 0
    while need > 0:
        item = bare_event(f'X{added}')
        for name in ATTRIBUTES:
            take = min(schema.BOUNDS['attribute_passages'], need)
            item[name]['passages'] = ['P1'] * take
            need -= take
        value['events'].append(item)
        added += 1
    assert cited(value) == total
    return value


class ReadTestCase(SimpleTestCase):
    def refused(self, value, stage: str, reason: str):
        """``value`` (an answer, or its text when a str) is refused whole at ``stage`` with exactly ``reason``."""
        result = read.read(value if isinstance(value, str) or value is None else text(value))
        self.assertIsInstance(result, read.Refusal)
        self.assertEqual((result.stage, result.reason), (stage, f'{REFUSED}{reason}.'))
        self.assertIs(result.refused, True)
        return result

    def accepted(self, value) -> dict:
        result = read.read(text(value))
        self.assertNotIsInstance(result, read.Refusal, getattr(result, 'reason', ''))
        self.assertEqual(result, value)  # exactly as parsed: nothing repaired, coerced, truncated or dropped
        return result


class GoodAnswerTests(ReadTestCase):
    def test_a_good_answer_is_read_exactly_as_parsed(self):
        value = answer()
        result = self.accepted(value)
        self.assertEqual(json.dumps(result, sort_keys=True), json.dumps(json.loads(text(value)), sort_keys=True))
        self.assertEqual(self.accepted(answer(passages=[], lesions=[], events=[], open_questions=[]))['events'], [])

    def test_the_adjudicated_values_are_read(self):
        value = answer()
        self.assertEqual(value['events'][2]['scope']['value'], 'exceptive')  # C-7
        self.accepted(value)
        for region in ('right_colon', 'left_colon', 'proximal_colon', 'distal_colon'):  # C-15
            with self.subTest(landmark=region):
                changed = answer(lesions=[lesion(landmark=region)])
                changed['events'][1]['target']['landmark'] = region
                changed['encounter']['anatomy'] = [{'state': 'absent', 'landmark': region, 'words': '', 'passages': []}]
                changed['encounter']['reach'][0]['landmark'] = region
                self.accepted(changed)

    def test_item_level_findings_never_refuse_the_answer(self):
        def change(edit):
            value = answer()
            edit(value)
            return value

        findings = {
            'a passage id cited but not defined': lambda v: v['events'][1]['kind'].update(passages=['P99']),
            'a lesion id not defined': lambda v: v['events'][1]['target'].update(lesion='L99'),
            'part_of naming no event': lambda v: v['events'][1].update(part_of='E99'),
            'part_of naming itself': lambda v: v['events'][1].update(part_of='E1'),
            'a contradiction with no such event': lambda v: v['events'][1]['contradicts'].append(
                {'event': 'E99', 'passages': ['P3']}),
            'a reach naming no event': lambda v: v['encounter']['reach'][0].update(event='E99'),
            'visit facts on an event that is no visit': lambda v: v['encounter']['visit_facts'].append(
                {'event': 'E1', 'basis': attribute('total_time', '25 minutes', ['P1']),
                 'separately_identifiable': attribute('not_stated')}),
            'a scope on a performed event': lambda v: v['events'][1]['scope'].update(value='single_target'),
            'listed targets that are not lesions': lambda v: v['events'][2]['scope'].update(
                value='listed_targets', targets=['L7', 'L8']),
            'one passage id twice in a list': lambda v: v['events'][1]['kind'].update(passages=['P2', 'P2']),
            'an open question naming nothing defined': lambda v: v['open_questions'].append(
                {'about': 'identity', 'events': ['E99'], 'lesions': ['L99'], 'passages': ['P99']}),
            'a stated date with no value': lambda v: v['encounter']['date_of_service'].update(value=''),
            'a date not stated but given': lambda v: v['encounter']['date_of_service'].update(state='not_stated'),
            'several dates and a value': lambda v: v['encounter']['date_of_service'].update(state='several'),
            'an umbrella on a positive event': lambda v: v['events'][1]['kind'].update(value='intervention'),
            'performed in the future': lambda v: v['events'][1]['time'].update(value='future'),
            'a passage too short to locate': lambda v: v['passages'].append({'id': 'P4', 'text': 'No.'}),
            'words found in no passage': lambda v: v['events'][1]['kind'].update(words='excised'),
            'one id in two lists': lambda v: v['lesions'].append(lesion('E1')),
            'the largest sequence': lambda v: v['events'][1].update(sequence=999),
        }
        for name, edit in findings.items():
            with self.subTest(finding=name):
                self.accepted(change(edit))


class JsonRowTests(ReadTestCase):
    def test_strict_json(self):
        good = text(answer())
        rows = {
            'no text': (None, 'there is no answer text'),
            'bytes': (good.encode(), 'there is no answer text'),
            'empty': ('', 'the answer is not valid JSON (Expecting value at character 0)'),
            'trailing text': (good + ' x', f'the answer is not valid JSON (Extra data at character {len(good) + 1})'),
            'a code fence': ('```json\n' + good + '\n```', 'the answer is not valid JSON (Expecting value at character 0)'),
            'a repeated key': ('{"passages": [], "passages": []}',
                               'the answer repeats a JSON object key, so its meaning is ambiguous'),
            'NaN': ('{"a": NaN}', 'the answer contains a non-finite number'),
            'Infinity': ('{"a": -Infinity}', 'the answer contains a non-finite number'),
            'a number too large': ('{"a": 1e400}', 'the answer contains a number too large to represent'),
            'NUL': ('{"a": "\\u0000"}', 'the answer contains NUL or unpaired surrogate characters'),
            'a lone surrogate': ('{"a": "\\ud800"}', 'the answer contains NUL or unpaired surrogate characters'),
        }
        for name, (value, reason) in rows.items():
            with self.subTest(json=name):
                if not isinstance(value, str):
                    result = read.read(value)
                    self.assertEqual((result.stage, result.reason), ('json', f'{REFUSED}{reason}.'))
                else:
                    self.refused(value, 'json', reason)


class SchemaRowTests(ReadTestCase):
    def test_the_schema(self):
        def change(edit):
            value = answer()
            edit(value)
            return value

        breach = 'the answer breaks the interpretation schema: '
        rows = {
            'not an object': ([], 'the interpretation is not an object'),
            'a missing field': (change(lambda v: v.pop('events')),
                                "the interpretation lacks the required field 'events'"),
            'an added field': (change(lambda v: v.update(notes=[])),
                               "the interpretation has a field the schema does not allow ('notes')"),
            'an added nested field': (change(lambda v: v['events'][1]['time'].update(note='')),
                                      "events[1].time has a field the schema does not allow ('note')"),
            'a missing nested field': (change(lambda v: v['events'][1].pop('contradicts')),
                                       "events[1] lacks the required field 'contradicts'"),
            'the legacy specimen kind': (change(lambda v: v['events'][1]['kind'].update(value='specimen')),
                                         'events[1].kind.value is not one of the values the schema allows'),
            'a landmark written as words': (change(lambda v: v['lesions'][0].update(landmark='right colon')),
                                            'lesions[0].landmark is not one of the values the schema allows'),
            'a scope outside the list': (change(lambda v: v['events'][2]['scope'].update(value='except')),
                                         'events[2].scope.value is not one of the values the schema allows'),
            'a boolean sequence': (change(lambda v: v['events'][1].update(sequence=True)),
                                   'events[1].sequence is not an integer'),
            'a fractional sequence': (change(lambda v: v['events'][1].update(sequence=2.0)),
                                      'events[1].sequence is not an integer'),
            'a sequence as text': (change(lambda v: v['events'][1].update(sequence='2')),
                                   'events[1].sequence is not an integer'),
            'null for a string': (change(lambda v: v['events'][1].update(part_of=None)),
                                  'events[1].part_of is not a string'),
            'a string for a list': (change(lambda v: v['events'][1]['kind'].update(passages='P2')),
                                    'events[1].kind.passages is not a list'),
        }
        for name, (value, reason) in rows.items():
            with self.subTest(schema=name):
                self.refused(value, 'schema', breach + reason)


class BoundTests(ReadTestCase):
    """Each bound at its limit is read, and one past it is refused, named by count and never truncated."""

    def at_and_past(self, build, limit: int, reason: str):
        self.accepted(build(limit))
        self.refused(build(limit + 1), 'bounds', reason.format(n=f'{limit + 1:,}', limit=f'{limit:,}'))

    def test_the_top_level_lists(self):
        def passages(n):
            return answer(passages=[{'id': f'P{i + 1}', 'text': f'Synthetic passage number {i + 1}.'}
                                    for i in range(n)])

        self.at_and_past(passages, 400, 'it lists {n} passages, more than the {limit} this contract accepts')
        self.at_and_past(lambda n: answer(lesions=[lesion(f'L{i}') for i in range(n)]), 64,
                         'it lists {n} lesions, more than the {limit} this contract accepts')
        self.at_and_past(lambda n: answer(events=[event(f'E{i}') for i in range(n)]), 200,
                         'it lists {n} events, more than the {limit} this contract accepts')
        question = {'about': 'time', 'events': ['E1'], 'lesions': [], 'passages': ['P2']}
        self.at_and_past(lambda n: answer(open_questions=[copy.deepcopy(question) for _ in range(n)]), 32,
                         'it lists {n} open questions, more than the {limit} this contract accepts')

    def test_the_encounter_lists(self):
        entries = {
            'team': ({'words': 'Synthetic Fellow, MD', 'passages': []}, 8, 'team members'),
            'anatomy': ({'state': 'absent', 'landmark': 'sigmoid_colon', 'words': '', 'passages': []}, 16,
                        'anatomy entries'),
            'reach': ({'event': 'E0', 'landmark': 'cecum', 'words': '', 'passages': [],
                       'completion': attribute('complete')}, 16, 'reach entries'),
            'visit_facts': ({'event': 'E1', 'basis': attribute('not_stated'),
                             'separately_identifiable': attribute('not_stated')}, 8, 'visit facts'),
        }
        for key, (entry, limit, label) in entries.items():
            with self.subTest(list=key):
                def build(n, key=key, entry=entry):
                    value = answer()
                    value['encounter'][key] = [copy.deepcopy(entry) for _ in range(n)]
                    return value

                self.at_and_past(build, limit, f'encounter.{key} lists {{n}} {label}, more than the {{limit}} this '
                                               'contract accepts')

        def other_dates(n):
            value = answer()
            value['encounter']['date_of_service']['other_dates'] = [
                {'value': '', 'role': 'unclear', 'words': '', 'passages': []} for _ in range(n)]
            return value

        self.at_and_past(other_dates, 16, 'encounter.date_of_service.other_dates lists {n} other dates, more than the '
                                          '{limit} this contract accepts')

    def test_a_passage_text(self):
        def passage(size):
            value = answer()
            value['passages'][1]['text'] = ('Synthetic passage ' * 40)[:size]
            return value

        self.accepted(passage(1))
        self.refused(passage(0), 'bounds', 'passages[1].text is empty; a passage has at least 1 character')
        self.at_and_past(passage, 600, 'passages[1].text has {n} characters, more than the {limit} one passage may have')

    def test_the_lists_inside_an_item(self):
        def at(path):
            def build(n):
                value = answer()
                node = value
                for step in path[:-1]:
                    node = node[step]
                node[path[-1]] = ([{'event': 'E2', 'passages': ['P3']} for _ in range(n)] if path[-1] == 'contradicts'
                                  else [f'L{i}' for i in range(n)] if path[-1] == 'targets'
                                  else ['E1'] * n if path[-1] == 'events'
                                  else ['L1'] * n if path[-1] == 'lesions'
                                  else ['P2'] * n)
                return value
            return build

        question = {'about': 'identity', 'events': [], 'lesions': [], 'passages': []}
        cases = (
            (('events', 1, 'kind', 'passages'), 8, 'events[1].kind.passages lists {n} passage ids, more than the {limit} '
                                                   'one passages list may have'),
            (('events', 1, 'target', 'passages'), 8, 'events[1].target.passages lists {n} passage ids, more than the '
                                                     '{limit} one passages list may have'),
            (('lesions', 0, 'passages'), 8, 'lesions[0].passages lists {n} passage ids, more than the {limit} one '
                                            'passages list may have'),
            (('encounter', 'date_of_service', 'passages'), 8, 'encounter.date_of_service.passages lists {n} passage '
                                                              'ids, more than the {limit} one passages list may have'),
            (('encounter', 'reach', 0, 'completion', 'passages'), 8, 'encounter.reach[0].completion.passages lists {n} '
                                                                     'passage ids, more than the {limit} one passages '
                                                                     'list may have'),
            (('events', 1, 'contradicts'), 8, 'events[1].contradicts lists {n} contradictions, more than the {limit} '
                                              'one event may have'),
            (('events', 2, 'scope', 'targets'), 16, 'events[2].scope.targets lists {n} targets, more than the {limit} '
                                                    'one scope may have'),
        )
        for path, limit, reason in cases:
            with self.subTest(list='.'.join(map(str, path))):
                self.at_and_past(at(path), limit, reason)

        def contradiction_passages(n):
            value = answer()
            value['events'][1]['contradicts'] = [{'event': 'E2', 'passages': ['P3'] * n}]
            return value

        self.at_and_past(contradiction_passages, 8, 'events[1].contradicts[0].passages lists {n} passage ids, more '
                                                    'than the {limit} one passages list may have')
        for key in ('events', 'lesions', 'passages'):
            with self.subTest(open_question=key):
                def build(n, key=key):
                    value = answer(open_questions=[copy.deepcopy(question)])
                    value['open_questions'][0][key] = {'events': ['E1'], 'lesions': ['L1'], 'passages': ['P2']}[key] * n
                    return value

                self.at_and_past(build, 16, f'open_questions[0].{key} lists {{n}} ids, more than the {{limit}} one '
                                            'open question list may have')

    def test_every_words_field(self):
        def at(where):
            def build(n):
                value = answer()
                node = value
                for step in where[:-1]:
                    node = node[step]
                node[where[-1]] = ('synthetic words ' * 30)[:n]
                return value
            return build

        for where in (('events', 1, 'time', 'words'), ('events', 1, 'target', 'words'), ('events', 2, 'scope', 'words'),
                      ('lesions', 0, 'words'), ('lesions', 0, 'site_words'), ('lesions', 0, 'size_words'),
                      ('encounter', 'documenting_endoscopist', 'words'), ('encounter', 'date_of_service', 'words'),
                      ('encounter', 'reach', 0, 'completion', 'words')):
            path = '.'.join(f'[{step}]' if isinstance(step, int) else step for step in where).replace('.[', '[')
            with self.subTest(words=path):
                self.at_and_past(at(where), 300, f'{path} has {{n}} characters, more than the {{limit}} one words field '
                                                 'may have')

    def test_the_sequence(self):
        def sequence(n):
            value = answer()
            value['events'][1]['sequence'] = n
            return value

        self.accepted(sequence(0))
        self.accepted(sequence(999))
        self.refused(sequence(1000), 'bounds', 'events[1].sequence is 1,000, outside 0 to 999')
        self.refused(sequence(-1), 'bounds', 'events[1].sequence is -1, outside 0 to 999')
        self.refused(sequence(10 ** 30), 'bounds', 'events[1].sequence is over a million, outside 0 to 999')
        self.refused(sequence(-10 ** 30), 'bounds', 'events[1].sequence is below minus a million, outside 0 to 999')

    def test_the_passage_ids_cited_in_the_whole_answer(self):
        self.accepted(with_cited(4000))
        self.refused(with_cited(4001), 'bounds', 'it cites 4,001 passage ids in all, more than the 4,000 this contract '
                                                 'accepts')
        question = with_cited(4000)
        question['open_questions'] = [{'about': 'time', 'events': [], 'lesions': [], 'passages': ['P1']}]
        self.refused(question, 'bounds', 'it cites 4,001 passage ids in all, more than the 4,000 this contract accepts')

    def test_a_top_level_bound_is_named_before_an_item_bound(self):
        value = answer(events=[event(f'E{i}') for i in range(201)])
        value['events'][0]['kind']['passages'] = ['P2'] * 9
        self.refused(value, 'bounds', 'it lists 201 events, more than the 200 this contract accepts')


class IdRowTests(ReadTestCase):
    def test_an_id_must_be_an_id(self):
        for key in ('passages', 'lesions', 'events'):
            for bad in ('', '-P1', '_P1', 'P' * 25, 'P 1', 'P1\n', 'Pé1', 'Ｐ1', 'P1/2', 'P1#'):
                with self.subTest(list=key, id=repr(bad)):
                    value = answer()
                    value[key][0]['id'] = bad
                    self.refused(value, 'ids', f'{key}[0].id is not an id: 1 to 24 letters, digits, "_", ".", ":" or '
                                               '"-", beginning with a letter or a digit')
        for good in ('P' + '1' * 23, 'a', '7', 'P1_a.b:c-d'):
            with self.subTest(id=good):
                value = answer()
                value['passages'][0]['id'] = good
                self.accepted(value)

    def test_an_id_is_unique_in_its_list(self):
        rows = {'passages': ('passages', 2, 'P1'), 'lesions': ('lesions', 1, 'L1'), 'events': ('events', 2, 'E0')}
        for key, (label, index, repeated) in rows.items():
            with self.subTest(list=key):
                value = answer()
                if key == 'lesions':
                    value['lesions'].append(lesion('L1'))
                else:
                    value[key][index]['id'] = repeated
                first = 0
                self.refused(value, 'ids', f'two {label} share one id ({key}[{first}] and {key}[{index}])')


class DateRowTests(ReadTestCase):
    def test_a_date_is_empty_or_a_real_iso_date(self):
        for good in ('', '2026-03-14', '2024-02-29', '1999-12-31'):
            with self.subTest(date=good):
                value = answer()
                value['encounter']['date_of_service']['value'] = good
                value['encounter']['date_of_service']['other_dates'] = [
                    {'value': good, 'role': 'birth', 'words': '', 'passages': []}]
                self.accepted(value)
        for bad in ('2026-02-30', '2025-02-29', '03/14/2026', '2026-3-14', '2026-03-14T09:00', ' 2026-03-14',
                    '２０２６-03-14', '0000-01-01', 'March 14, 2026', MODEL_TEXT):
            with self.subTest(date=bad):
                value = answer()
                value['encounter']['date_of_service']['value'] = bad
                self.refused(value, 'schema', 'a date is not YYYY-MM-DD (encounter.date_of_service.value)')
                value = answer()
                value['encounter']['date_of_service']['other_dates'] = [
                    {'value': '2026-01-02', 'role': 'other_document', 'words': '', 'passages': []},
                    {'value': bad, 'role': 'report_time', 'words': '', 'passages': []}]
                self.refused(value, 'schema', 'a date is not YYYY-MM-DD, YYYY-MM or YYYY '
                                              '(encounter.date_of_service.other_dates[1].value)')

    def test_an_other_date_of_another_role_may_be_a_month_or_a_year(self):
        # the FRESH recording (S16): Gemini writes a history date the document gives with no day at its own precision
        # ("January 2024" -> "2024-01", "in 2017" -> "2017"); refusing the whole answer for it refused 27 of 69 answers
        for role in ('birth', 'other_occurrence', 'other_document', 'report_time', 'unclear'):
            for good in ('2024', '2024-01', '1999-12', '2026-11-08'):
                with self.subTest(role=role, date=good):
                    value = answer()
                    value['encounter']['date_of_service']['other_dates'] = [
                        {'value': good, 'role': role, 'words': '', 'passages': []}]
                    self.accepted(value)
            for bad in ('2024-13', '2024-00', '0000', '0000-01', '24', '2024-1', '202401', '2024-01-', 'Jan 2024',
                        '２０２４', ' 2024', '2024 '):
                with self.subTest(role=role, date=bad):
                    value = answer()
                    value['encounter']['date_of_service']['other_dates'] = [
                        {'value': bad, 'role': role, 'words': '', 'passages': []}]
                    self.refused(value, 'schema', 'a date is not YYYY-MM-DD, YYYY-MM or YYYY '
                                                  '(encounter.date_of_service.other_dates[0].value)')

    def test_the_date_of_service_and_this_encounters_other_dates_stay_full_dates(self):
        for partial in ('2026', '2026-11'):
            with self.subTest(date=partial):
                value = answer()
                value['encounter']['date_of_service']['value'] = partial
                self.refused(value, 'schema', 'a date is not YYYY-MM-DD (encounter.date_of_service.value)')
                value = answer()
                value['encounter']['date_of_service']['other_dates'] = [
                    {'value': '2024', 'role': 'other_occurrence', 'words': '', 'passages': []},
                    {'value': partial, 'role': 'this_encounter', 'words': '', 'passages': []}]
                self.refused(value, 'schema', 'a date is not YYYY-MM-DD '
                                              '(encounter.date_of_service.other_dates[1].value)')


class OrderTests(ReadTestCase):
    def test_the_first_failing_step_refuses_the_whole_answer(self):
        both = answer()
        both['events'][1]['kind']['passages'] = ['P2'] * 9  # a bound
        both['events'][1]['id'] = 'E0'  # and a repeated id
        self.assertEqual(read.read(text(both)).stage, 'bounds')
        ids = answer()
        ids['events'][1]['id'] = 'E0'
        ids['encounter']['date_of_service']['value'] = '2026-02-30'
        self.assertEqual(read.read(text(ids)).stage, 'ids')
        schema_first = answer()
        schema_first['events'][1]['sequence'] = True
        schema_first['events'][1]['kind']['passages'] = ['P2'] * 9
        self.assertEqual(read.read(text(schema_first)).stage, 'schema')
        self.assertEqual(read.read(text(answer())[:-1]).stage, 'json')


class WordingTests(ReadTestCase):
    def test_no_refusal_repeats_the_models_text(self):
        def change(edit):
            value = answer()
            edit(value)
            return value

        planted = {
            'a words field too long': change(lambda v: v['events'][1]['time'].update(words=MODEL_TEXT * 13)),
            'a passage too long': change(lambda v: v['passages'][1].update(text=MODEL_TEXT * 25)),
            'an id that is not one': change(lambda v: v['events'][1].update(id=MODEL_TEXT + '-NOT-AN-ID')),
            'a repeated id': change(lambda v: [item.update(id=MODEL_TEXT[:24]) for item in v['events'][:2]]),
            'a date that is not one': change(lambda v: v['encounter']['date_of_service'].update(value=MODEL_TEXT)),
            'an enumeration value': change(lambda v: v['events'][1]['kind'].update(value=MODEL_TEXT)),
            'a field the schema lacks': change(lambda v: v['events'][1].update({MODEL_TEXT: ''})),
            'a sequence': change(lambda v: v['events'][1].update(sequence=int('1' + '0001' * 6))),
        }
        for name, value in planted.items():
            with self.subTest(planted=name):
                result = read.read(text(value))
                self.assertIsInstance(result, read.Refusal)
                for piece in (MODEL_TEXT, MODEL_TEXT[:12], '10001'):
                    self.assertNotIn(piece, result.reason)
        broken = text(answer()).replace('"P3"', f'"{MODEL_TEXT}" "P3"', 1)
        self.assertNotIn(MODEL_TEXT, read.read(broken).reason)  # a JSON error names a position only


class RefusalTests(SimpleTestCase):
    def test_a_refusal_is_one_cpt_studio_sentence_at_a_known_stage(self):
        self.assertEqual(read.STAGES, ('envelope', 'json', 'schema', 'bounds', 'ids'))
        made = read.refuse('envelope', 'the answer ended at the output limit (MAX_TOKENS)')
        self.assertEqual(made, read.Refusal(stage='envelope', reason=f'{REFUSED}the answer ended at the output limit '
                                                                     '(MAX_TOKENS).'))
        self.assertEqual(read.refuse('json', 'it stops.').reason, f'{REFUSED}it stops.')
        self.assertEqual(to_jsonable(made), {'stage': 'envelope', 'refused': True,
                                             'reason': f'{REFUSED}the answer ended at the output limit (MAX_TOKENS).'})
        # the participants' prefix is not this one: a reading's refusal is never stored as an interpretation's
        for stage, reason, refused in (('other', f'{REFUSED}why.', True), ('json', 'why.', True),
                                       ('json', 'The reading was not used: the answer is not valid JSON.', True),
                                       ('json', f'{REFUSED}why', True), ('json', f'{REFUSED}.', True),
                                       ('json', None, True), ('json', f'{REFUSED}why.', False)):
            with self.subTest(stage=stage, reason=reason, refused=refused):
                with self.assertRaises(ValueError):
                    read.Refusal(stage=stage, reason=reason, refused=refused)
        with self.assertRaises(ValueError):
            read.refuse('json', '')

    def test_an_answer_is_read_only_under_the_local_schemas_pin(self):
        changed = copy.deepcopy(schema.LOCAL_SCHEMA)
        changed['properties']['events']['items']['properties']['kind']['properties']['value']['enum'].append('specimen')
        with mock.patch.object(schema, 'LOCAL_SCHEMA', changed):
            with self.assertRaisesRegex(RuntimeError, 'needs a new INTERPRETATION_VERSION'):
                read.read(text(answer()))
        self.assertNotIsInstance(read.read(text(answer())), read.Refusal)  # the positive control, unchanged
