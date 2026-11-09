"""The persisted event inventory (Gemini migration slice S01; design/contract.md 4.2-4.5 and 8.1, design/FINAL.md 4.1),
TEXT-ONLY: the fields of a read row and of a refused row, their sha256 over every field and binding, a round trip
through JSON and through model-like objects, and the versioned reader that RAISES - on an unknown version pair, an
unknown shape anywhere in the stored content, a refused row carrying content, a report that names another label,
request or response, a changed row, a row bound to another text or response - and never answers with None or an empty
inventory: a refused row's events cannot be read at all. Synthetic content built in code; no database."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from studio.interpretation import INTERPRETATION_VERSION, INVENTORY_VERSION, LABEL, read, store
from studio.interpretation import ADAPTER_VERSION, PROVIDER, PURPOSE
from studio.models import EventInventory, ProviderRun, SourceRevision

from tests.support import factories as f

ENCOUNTER = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0001'
REVISION = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0002'
RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0003'
TEXT_SHA256 = '1' * 64
REQUEST_SHA256 = '2' * 64
RESPONSE_SHA256 = '3' * 64
DOCUMENT_TEXT = 'SYNTHETIC-DOCUMENT-TEXT-0001'  # a stored slice of the revision text: never repeated in an error
P1 = 'Synthetic colonoscopy note. Date of service: 03/14/2026.'
P2 = 'A 7 mm sessile polyp (transverse colon) was removed with a cold snare.'


def span(start: int, text: str) -> dict:
    return {'start': start, 'end': start + len(text), 'text': text}


def words(start: int, text: str, match: str = 'exact', **extra) -> dict:
    return {**span(start, text), 'match': match, **extra}


def attribute(value, basis='stated', state='verified', words=None, passages=(), checks=(), literals=None, reasons=(),
              open=False, **extra) -> dict:
    return {'value': value, 'basis': basis, 'state': state, 'open': open, 'words': words, 'passages': list(passages),
            'checks': list(checks), 'literals': literals or {}, 'reasons': list(reasons), **extra}


def default(value) -> dict:
    return attribute(value, basis='default', checks=['default'])


def absent(value) -> dict:
    return attribute(value, basis='absent', state='absent')


def event(id: str, **changes) -> dict:
    item = {
        'id': id, 'family': 'gi.colonoscopy',
        'procedure': default('colonoscopy'),
        'kind': attribute('snare', words=words(70, 'removed'), passages=['P2'],
                          checks=['passages_located', 'words_in_own_passage']),
        'technique': attribute('cold_snare', words=words(91, 'cold snare'), passages=['P2'], checks=['device_words']),
        'target': attribute('transverse_colon', words=words(58, 'A 7 mm sessile polyp', occurrences=1), passages=['P2'],
                            lesion='L1', identity='verified', identity_by=['statement_tie', 'size_literal']),
        'time': default('current_encounter'),
        'performer': default('documenting_team'),
        'status': attribute('performed', words=words(66, 'was removed with a cold snare', 'normalized'),
                            passages=['P2']),
        'scope': absent('not_applicable'),
        'purpose': attribute('removal', words=words(70, 'removed'), passages=['P2']),
        'part_of': '', 'sequence': 0, 'extent': None, 'completion': None, 'visit': None,
        'catalogue_kind': 'snare', 'code_technique': 'snare', 'positive': True, 'current': 'yes',
        'key': {'family': 'gi.colonoscopy', 'kind': 'snare', 'lesion': 'L1'},
    }
    item.update(changes)
    return item


def content() -> dict:
    """Synthetic stored content in every shape the contract gives: located, ambiguous and unlocated passages; a lesion;
    an examination with its extent and completion, a performed removal, an exceptive denial and a visit; relations; the
    encounter facts; an open question; and the verification report as normalization gives it."""
    return {
        'events': {
            'passages': [
                {'id': 'P1', 'state': 'located', 'spans': [span(0, P1)], 'reason': '', 'chars': len(P1), 'extended': ''},
                {'id': 'P2', 'state': 'ambiguous', 'spans': [span(58, P2), span(400, P2)], 'reason': '',
                 'chars': len(P2), 'extended': 'closing_bracket'},
                {'id': 'P3', 'state': 'unlocated', 'spans': [], 'reason': 'not found', 'chars': 27, 'extended': ''},
            ],
            'lesions': [{
                'id': 'L1', 'words': words(60, '7 mm sessile polyp'), 'landmark': 'transverse_colon',
                'site': attribute('transverse_colon', words=words(85, 'transverse colon'), passages=['P2']),
                'size': {'mm': [7, 7.5], 'span': words(60, '7 mm')}, 'multiplicity': 'single', 'passages': ['P2'],
                'state': 'verified', 'reasons': [], 'distinct_from': [], 'possibly_same_as': ['L2'],
            }],
            'events': [
                event('E0', kind=attribute('examination', words=words(10, 'colonoscopy'), passages=['P1']),
                      technique=default('endoscope'), target=absent('not_stated') | {
                          'lesion': '', 'identity': 'none', 'identity_by': None},
                      purpose=absent('not_stated'), sequence=attribute(1, passages=['P1']),
                      extent=attribute('cecum', words=words(200, 'cecum'), passages=['P1']),
                      completion=attribute('complete', basis='absent', state='absent'), positive=True,
                      catalogue_kind='', code_technique='', key={}),
                event('E1'),
                event('E2', kind=attribute('removal', words=words(300, 'removed'), passages=['P3'],
                                           state='unverified', reasons=['passage_unlocated']),
                      status=attribute('not_performed', words=words(290, 'No other polyp was removed'), passages=['P3'],
                                       literals={'negators': ['No']}),
                      scope=attribute('exceptive', words=words(290, 'No other'), passages=['P3'], targets=[]),
                      target=absent('not_stated') | {'lesion': '', 'identity': 'none', 'identity_by': None},
                      part_of=attribute('', basis='absent', state='absent'), positive=False, current='unresolved'),
                event('E3', kind=attribute('em_visit'), family='gi.office_em',
                      visit={'basis': attribute('total_time', literals={'minutes': [25]}),
                             'separately_identifiable': absent('not_stated')}),
            ],
            'relations': [
                {'id': 'R1', 'type': 'independent', 'statement': 'E2', 'event': 'E1', 'attribute': 'scope',
                 'reason': 'exceptive', 'claimed_by_model': False, 'passages': ['P3']},
                {'id': 'R2', 'type': 'dismissed_claim', 'statement': 'E2', 'event': 'E1', 'attribute': 'target',
                 'reason': 'claim_unknown_event', 'claimed_by_model': True, 'passages': []},
            ],
        },
        'encounter_facts': {
            'date_of_service': {
                'state': 'stated', 'value': '2026-03-14', 'verified': True, 'words': words(45, '03/14/2026'),
                'passages': ['P1'], 'reasons': [], 'candidates': [], 'readings': ['2026-03-14'],
                'others': {'birth': [{'value': '1960-01-02', 'verified': True, 'passages': ['P1']}],
                           'other_occurrence': [], 'other_document': [], 'report_time': [], 'unclear': []},
            },
            'documenting_endoscopist': {'span': None, 'tokens': []},
            'team': [{'span': span(500, 'Synthetic Fellow'), 'tokens': ['synthetic', 'fellow']}],
            'anatomy': [],
            'reach': [{'event': 'E0', 'family': 'gi.colonoscopy', 'landmark': 'cecum', 'state': 'verified'}],
            'visits': [{'event': 'E3', 'basis': 'total_time'}],
            'derived': {'current_families': ['gi.colonoscopy'],
                        'procedure_day': {'performed': ['gi.colonoscopy'], 'possible': []}, 'absent': []},
        },
        'open_questions': [{'about': 'time', 'events': ['E1'], 'lesions': [], 'passages': ['P2'],
                            'attached_to': [{'event': 'E1', 'attribute': 'time'}]}],
        'verification': {
            'counts': {'time': {'claimed': 4, 'verified': 3, 'unverified': 0, 'absent': 0, 'discarded': 0, 'open': 1}},
            'reasons': {'passage_unlocated': 1}, 'relations': {'independent': 1, 'dismissed_claim': 1},
            'discarded': [{'where': 'reach[1]', 'reason': 'reach_not_permitted'}],
            'problems': ['passages[2] was not found in the revision text.'],
        },
    }


def read_row(**changes) -> dict:
    arguments = {'encounter_id': ENCOUNTER, 'revision_id': REVISION, 'provider_run_id': RUN,
                 'text_sha256': TEXT_SHA256, 'request_sha256': REQUEST_SHA256, 'response_sha256': RESPONSE_SHA256,
                 **content()}
    arguments.update(changes)
    return store.row(**arguments)


def refusal() -> read.Refusal:
    return read.refuse('bounds', 'it lists 201 events, more than the 200 this contract accepts')


def refused_row(**changes) -> dict:
    arguments = {'encounter_id': ENCOUNTER, 'revision_id': REVISION, 'provider_run_id': RUN,
                 'text_sha256': TEXT_SHA256, 'request_sha256': REQUEST_SHA256, 'response_sha256': RESPONSE_SHA256}
    arguments.update(changes)
    return store.refused_row(refusal(), **arguments)


def load(fields) -> store.StoredInventory:
    return store.load(fields, text_sha256=TEXT_SHA256, response_sha256=RESPONSE_SHA256)


def variant(fields: dict, edit, rehash: bool = True) -> dict:
    """A deep copy of ``fields`` changed by ``edit``, its sha256 recomputed (when it still can be), so that only the
    change itself is wrong."""
    changed = copy.deepcopy(fields)
    edit(changed)
    if rehash:
        try:
            changed['sha256'] = store.content_sha256(changed)
        except (store.StoreError, KeyError):
            pass
    return changed


class RowTests(SimpleTestCase):
    def test_a_read_row(self):
        fields = read_row()
        self.assertEqual(tuple(fields), store.FIELDS)
        self.assertEqual(store.FIELDS, ('encounter_id', 'revision_id', 'provider_run_id', 'interpretation_version',
                                        'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256', 'state',
                                        'events', 'encounter_facts', 'open_questions', 'verification', 'sha256'))
        self.assertEqual((fields['interpretation_version'], fields['inventory_version'], fields['state']),
                         ('gemini-events@1', 'gemini-inventory@1', 'read'))
        self.assertEqual(fields['verification'], {**content()['verification'], 'label': LABEL,
                                                   'request_sha256': REQUEST_SHA256,
                                                   'response_sha256': RESPONSE_SHA256, 'refused': False})
        loaded = load(fields)
        self.assertEqual((loaded.encounter_id, loaded.revision_id, loaded.provider_run_id), (ENCOUNTER, REVISION, RUN))
        self.assertEqual((loaded.events, loaded.encounter_facts, loaded.open_questions),
                         (content()['events'], content()['encounter_facts'], content()['open_questions']))
        self.assertEqual(loaded.verification, fields['verification'])
        self.assertEqual((loaded.refused, loaded.refusal, loaded.label, loaded.sha256),
                         (False, None, 'gemini-events@1+inventory@1', fields['sha256']))
        self.assertEqual(store.KNOWN_VERSIONS, frozenset({(INTERPRETATION_VERSION, INVENTORY_VERSION)}))

    def test_the_report_is_completed_or_must_already_agree(self):
        complete = dict(content()['verification'], label=LABEL, request_sha256=REQUEST_SHA256,
                        response_sha256=RESPONSE_SHA256, refused=False)
        self.assertEqual(read_row(verification=complete), read_row())
        for key, value in (('label', 'gemini-events@1+inventory@2'), ('request_sha256', '9' * 64),
                           ('response_sha256', '9' * 64), ('refused', True)):
            with self.subTest(report=key):
                with self.assertRaises(store.Mismatch):
                    read_row(verification=dict(content()['verification'], **{key: value}))
        with self.assertRaises(store.UnknownShape):
            read_row(verification=['not', 'a', 'report'])

    def test_nothing_the_reader_would_refuse_is_written(self):
        missing_time = content()['events']
        del missing_time['events'][1]['time']
        rows = {
            'an event without its time': dict(events=missing_time),
            'no derived facts': dict(encounter_facts={k: v for k, v in content()['encounter_facts'].items()
                                                      if k != 'derived'}),
            'an open question about billing': dict(open_questions=[{'about': 'billing', 'events': [], 'lesions': [],
                                                                    'passages': [], 'attached_to': []}]),
            'a binding that is no UUID': dict(revision_id='revision-1'),
            'a sha256 that is no sha256': dict(text_sha256='abc'),
            'content that is no JSON data': dict(open_questions=[{'about': 'time', 'events': {'E1'}, 'lesions': [],
                                                                 'passages': [], 'attached_to': []}]),
        }
        for name, changes in rows.items():
            with self.subTest(row=name):
                with self.assertRaises(store.UnknownShape):
                    read_row(**changes)

    def test_the_bindings_are_uuids_however_they_are_given(self):
        fields = read_row(encounter_id=uuid.UUID(ENCOUNTER), revision_id=REVISION.upper(),
                          provider_run_id=f'{{{RUN}}}')
        self.assertEqual((fields['encounter_id'], fields['revision_id'], fields['provider_run_id']),
                         (ENCOUNTER, REVISION, RUN))
        self.assertEqual(fields, read_row())

    def test_dataclasses_and_tuples_are_stored_as_json_data(self):
        events = content()['events']
        events['lesions'][0]['passages'] = ('P2',)
        self.assertEqual(read_row(events=events), read_row())


class ModelTests(SimpleTestCase):
    def test_the_fields_are_the_models_columns(self):
        columns = {item.attname: item for item in EventInventory._meta.concrete_fields}
        self.assertEqual(set(store.FIELDS), set(columns) - {'id', 'created_at'})  # FINAL 4.1: all but id, created_at
        self.assertEqual((EventInventory.READ, EventInventory.REFUSED), (store.READ, store.REFUSED))
        fields = read_row()
        for name in ('interpretation_version', 'inventory_version', 'text_sha256', 'request_sha256', 'response_sha256',
                     'state', 'sha256'):
            with self.subTest(column=name):
                self.assertLessEqual(len(fields[name]), columns[name].max_length)
        self.assertLessEqual(len(store.REFUSED), columns['state'].max_length)
        for name in ('events', 'encounter_facts', 'open_questions', 'verification'):
            with self.subTest(column=name):
                self.assertFalse(columns[name].null)  # a refused row still writes each of them


class HashTests(SimpleTestCase):
    def test_the_sha256_covers_every_field_and_the_bindings(self):
        fields = read_row()
        self.assertEqual(fields['sha256'], store.content_sha256(fields))
        self.assertEqual(read_row()['sha256'], fields['sha256'])  # stable
        changes = {'encounter_id': str(uuid.UUID(int=1)), 'revision_id': str(uuid.UUID(int=2)),
                   'provider_run_id': str(uuid.UUID(int=3)), 'interpretation_version': 'gemini-events@2',
                   'inventory_version': 'gemini-inventory@2', 'text_sha256': '4' * 64, 'request_sha256': '5' * 64,
                   'response_sha256': '6' * 64, 'state': 'refused', 'events': {}, 'encounter_facts': {},
                   'open_questions': [], 'verification': {}}
        self.assertEqual(set(changes), set(store.HASHED))
        for name, value in changes.items():
            with self.subTest(field=name):
                self.assertNotEqual(store.content_sha256(dict(fields, **{name: value})), fields['sha256'])
        self.assertEqual(store.content_sha256(dict(fields, sha256='0' * 64)), fields['sha256'])  # all but itself

    def test_a_database_round_trip_keeps_the_hash(self):
        fields = read_row()
        through_json = json.loads(json.dumps(fields))
        self.assertEqual(load(through_json).sha256, fields['sha256'])
        as_model = SimpleNamespace(**{**fields, 'encounter_id': uuid.UUID(ENCOUNTER), 'revision_id': uuid.UUID(REVISION),
                                      'provider_run_id': uuid.UUID(RUN), 'id': uuid.uuid4(), 'created_at': None})
        loaded = load(store.fields_of(as_model))
        self.assertEqual((loaded.sha256, loaded.encounter_id), (fields['sha256'], ENCOUNTER))
        with self.assertRaises(store.UnknownShape):
            store.fields_of(SimpleNamespace(**{key: value for key, value in fields.items() if key != 'state'}))


class VersionTests(SimpleTestCase):
    def test_an_unknown_version_raises(self):
        for name, value in (('interpretation_version', 'gemini-events@2'), ('interpretation_version', 'gi-routing@12'),
                            ('inventory_version', 'gemini-inventory@2'), ('inventory_version', ''),
                            ('interpretation_version', None), ('inventory_version', ['gemini-inventory@1'])):
            for state in ('read', 'refused'):
                with self.subTest(field=name, value=value, state=state):
                    fields = read_row() if state == 'read' else refused_row()
                    with self.assertRaises(store.UnknownVersion):
                        load(variant(fields, lambda f: f.update({name: value}), rehash=False))


class ShapeTests(SimpleTestCase):
    """Every way the stored content can be a shape this release does not know raises UnknownShape, with the sha256
    recomputed, so that the shape alone is wrong."""

    def assert_unknown(self, edit, fields=None):
        changed = variant(fields or read_row(), edit)
        with self.assertRaises(store.UnknownShape) as raised:
            load(changed)
        self.assertNotIn(DOCUMENT_TEXT, str(raised.exception))
        return str(raised.exception)

    def test_the_row(self):
        with self.assertRaises(store.UnknownShape):
            load([('state', 'read')])
        rows = {
            'a field missing': lambda f: f.pop('verification'),
            'an id': lambda f: f.update(id=str(uuid.uuid4())),
            'a created_at': lambda f: f.update(created_at='2026-11-09T10:00:00Z'),
            'an unknown state': lambda f: f.update(state='pending'),
            'a binding that is no UUID': lambda f: f.update(encounter_id='encounter-1'),
            'a binding of another type': lambda f: f.update(provider_run_id=3),
            'a text sha256 that is no sha256': lambda f: f.update(text_sha256='ABC'),
            'an upper-case sha256': lambda f: f.update(request_sha256='A' * 64),
        }
        for name, edit in rows.items():
            with self.subTest(row=name):
                self.assert_unknown(edit)
        for stored in (None, '0' * 63, 'Z' * 64):  # not recomputed, or the helper would mend it
            with self.subTest(stored_sha256=stored):
                with self.assertRaises(store.UnknownShape):
                    load(variant(read_row(), lambda f: f.update(sha256=stored), rehash=False))

    def test_the_events(self):
        def at(*path):
            def edit(value):
                def apply(f):
                    node = f
                    for step in path[:-1]:
                        node = node[step]
                    if value is KeyError:
                        del node[path[-1]]
                    else:
                        node[path[-1]] = value
                return apply
            return edit

        rows = {
            'no relations': at('events', 'relations')(KeyError),
            'an added container': at('events', 'notes')([]),
            'passages not a list': at('events', 'passages')({}),
            'a passage state': at('events', 'passages', 0, 'state')('found'),
            'a passage span without its end': at('events', 'passages', 0, 'spans', 0, 'end')(KeyError),
            'a passage extension': at('events', 'passages', 1, 'extended')('quote'),
            'an event without its time': at('events', 'events', 1, 'time')(KeyError),
            'an event with an added field': at('events', 'events', 1, 'excluded')(True),
            'a basis': at('events', 'events', 1, 'kind', 'basis')('guessed'),
            'an attribute state': at('events', 'events', 1, 'kind', 'state')('maybe'),
            'open as text': at('events', 'events', 1, 'kind', 'open')('false'),
            'a kind outside the schema': at('events', 'events', 1, 'kind', 'value')('specimen'),
            'a scope outside the schema': at('events', 'events', 2, 'scope', 'value')('except'),
            'a time outside the schema': at('events', 'events', 1, 'time', 'value')('today'),
            'a words match': at('events', 'events', 1, 'kind', 'words', 'match')('fuzzy'),
            'a words field it does not know': at('events', 'events', 1, 'kind', 'words', 'score')(1),
            'words that are text': at('events', 'events', 1, 'kind', 'words')(DOCUMENT_TEXT),
            'checks that are not a list': at('events', 'events', 1, 'kind', 'checks')('words_in_own_passage'),
            'literals that are not JSON': at('events', 'events', 2, 'status', 'literals', 'negators')(float('nan')),
            'a current': at('events', 'events', 1, 'current')('maybe'),
            'a positive as a number': at('events', 'events', 1, 'positive')(1),
            'an identity': at('events', 'events', 1, 'target', 'identity')('probable'),
            'a target without its lesion': at('events', 'events', 1, 'target', 'lesion')(KeyError),
            'a sequence as a boolean': at('events', 'events', 1, 'sequence')(True),
            'an extent that is text': at('events', 'events', 0, 'extent')('cecum'),
            'a completion outside the schema': at('events', 'events', 0, 'completion', 'value')('partial'),
            'a visit without its basis': at('events', 'events', 3, 'visit', 'basis')(KeyError),
            'a key that is a list': at('events', 'events', 1, 'key')([]),
            'a relation type': at('events', 'relations', 0, 'type')('veto'),
            'a model claim as a number': at('events', 'relations', 1, 'claimed_by_model')(1),
            'a lesion landmark in words': at('events', 'lesions', 0, 'landmark')('right colon'),
            'a size that is text': at('events', 'lesions', 0, 'size', 'mm')(['seven']),
            'a size that is infinite': at('events', 'lesions', 0, 'size', 'mm')([float('inf')]),
            'a lesion without its site': at('events', 'lesions', 0, 'site')(KeyError),
            'a key that is no string': at('events', 'events', 1, 'key')({1: 'x'}),
        }
        for name, edit in rows.items():
            with self.subTest(events=name):
                self.assert_unknown(edit)
        for key in ('passages', 'lesions', 'events', 'relations'):
            with self.subTest(repeated_id=key):
                message = self.assert_unknown(lambda f, key=key: f['events'][key].append(
                    copy.deepcopy(f['events'][key][0])))
                self.assertIn('repeats an id', message)

    def test_the_encounter_facts_open_questions_and_report(self):
        rows = {
            'no derived facts': lambda f: f['encounter_facts'].pop('derived'),
            'facts it does not know': lambda f: f['encounter_facts'].update(setting='office'),
            'a date of service in another form': lambda f: f['encounter_facts']['date_of_service'].update(
                value='03/14/2026'),
            'a date state': lambda f: f['encounter_facts']['date_of_service'].update(state='guessed'),
            'a reading in another form': lambda f: f['encounter_facts']['date_of_service'].update(readings=['2026-3-14']),
            'others without birth': lambda f: f['encounter_facts']['date_of_service']['others'].pop('birth'),
            'others with this encounter': lambda f: f['encounter_facts']['date_of_service']['others'].update(
                this_encounter=[]),
            'a team entry that is text': lambda f: f['encounter_facts'].update(team=['Synthetic Fellow']),
            'procedure day without possible': lambda f: f['encounter_facts']['derived']['procedure_day'].pop('possible'),
            'an open question about billing': lambda f: f['open_questions'][0].update(about='billing'),
            'an open question without attached_to': lambda f: f['open_questions'][0].pop('attached_to'),
            'open questions as an object': lambda f: f.update(open_questions={}),
            'a report without problems': lambda f: f['verification'].pop('problems'),
            'a count without open': lambda f: f['verification']['counts']['time'].pop('open'),
            'a reason count as text': lambda f: f['verification']['reasons'].update(passage_unlocated='1'),
            'a report sha256 that is no sha256': lambda f: f['verification'].update(request_sha256='x'),
            'a read report with a stage': lambda f: f['verification'].update(stage='bounds'),
        }
        for name, edit in rows.items():
            with self.subTest(content=name):
                self.assert_unknown(edit)

    def test_an_error_names_the_place_never_the_stored_text(self):
        message = self.assert_unknown(lambda f: f['events']['passages'][0].update(state=DOCUMENT_TEXT))
        self.assertIn('events.passages[0].state', message)
        message = self.assert_unknown(lambda f: f['events']['events'][1].update({DOCUMENT_TEXT + ' and more': 1}))
        self.assertIn('a key of 37 characters', message)


class MismatchTests(SimpleTestCase):
    def test_a_row_that_disagrees_with_itself_or_its_bindings(self):
        fields = read_row()
        rows = {
            'a changed sha256': variant(fields, lambda f: f.update(sha256='0' * 64), rehash=False),
            'content changed after it was hashed': variant(
                fields, lambda f: f['events']['events'][1]['status'].update(value='not_performed'), rehash=False),
            'a binding changed after it was hashed': variant(
                fields, lambda f: f.update(revision_id=str(uuid.UUID(int=9))), rehash=False),
            'a report naming another label': variant(
                fields, lambda f: f['verification'].update(label='gemini-events@1+inventory@2')),
            'a report naming another request': variant(fields, lambda f: f['verification'].update(
                request_sha256='9' * 64)),
            'a report naming another response': variant(fields, lambda f: f['verification'].update(
                response_sha256='9' * 64)),
            'a read row whose report says refused': variant(fields, lambda f: f['verification'].update(refused=True)),
        }
        for name, changed in rows.items():
            with self.subTest(row=name):
                with self.assertRaises(store.Mismatch):
                    load(changed)
        with self.assertRaisesRegex(store.Mismatch, 'another revision text'):
            store.load(fields, text_sha256='7' * 64, response_sha256=RESPONSE_SHA256)
        with self.assertRaisesRegex(store.Mismatch, 'another response'):
            store.load(fields, text_sha256=TEXT_SHA256, response_sha256='7' * 64)
        with self.assertRaises(store.Mismatch):
            store.load(fields, text_sha256='', response_sha256=RESPONSE_SHA256)
        self.assertEqual(load(fields).sha256, fields['sha256'])  # the positive control: unchanged, it loads

    def test_every_store_error_is_a_value_error_and_none_is_returned(self):
        for kind in (store.UnknownVersion, store.UnknownShape, store.Mismatch):
            self.assertTrue(issubclass(kind, store.StoreError) and issubclass(kind, ValueError))


class RefusedRowTests(SimpleTestCase):
    def test_a_refused_row(self):
        fields = refused_row()
        self.assertEqual(tuple(fields), store.FIELDS)
        self.assertEqual((fields['state'], fields['events'], fields['encounter_facts'], fields['open_questions']),
                         ('refused', store.EMPTY_EVENTS, {}, []))
        self.assertEqual(fields['verification'], {
            'label': LABEL, 'request_sha256': REQUEST_SHA256, 'response_sha256': RESPONSE_SHA256, 'counts': {},
            'reasons': {}, 'relations': {}, 'discarded': [], 'refused': True, 'stage': 'bounds',
            'problems': ['The interpretation was not used: it lists 201 events, more than the 200 this contract '
                         'accepts.']})
        loaded = load(fields)
        self.assertTrue(loaded.refused)
        self.assertEqual(loaded.refusal, refusal())
        self.assertNotEqual(fields['sha256'], read_row()['sha256'])

    def test_a_refused_answer_is_never_read_as_one_that_documents_nothing(self):
        loaded = load(refused_row())
        for name in ('events', 'encounter_facts', 'open_questions'):
            with self.subTest(content=name):
                with self.assertRaisesRegex(store.StoreError, 'was refused'):
                    getattr(loaded, name)
        self.assertEqual(load(read_row()).events['events'][1]['id'], 'E1')  # the positive control
        self.assertFalse(hasattr(loaded, 'content'))  # no public way around the properties

    def test_a_refused_row_carries_nothing_but_its_refusal(self):
        fields = refused_row()
        unknown = {
            'events': lambda f: f['events']['events'].append({'id': 'E1'}),
            'encounter facts': lambda f: f.update(encounter_facts=content()['encounter_facts']),
            'an open question': lambda f: f.update(open_questions=content()['open_questions']),
            'counts': lambda f: f['verification'].update(counts={'time': {}}),
            'two problems': lambda f: f['verification']['problems'].append('Another problem.'),
            'no problem': lambda f: f['verification'].update(problems=[]),
            'a problem that is no refusal': lambda f: f['verification'].update(problems=['It went wrong.']),
            'a reading\'s refusal': lambda f: f['verification'].update(problems=[
                'The reading was not used: it lists 201 events, more than the 200 this contract accepts.']),
            'an unknown stage': lambda f: f['verification'].update(stage='network'),
            'no stage': lambda f: f['verification'].pop('stage'),
        }
        for name, edit in unknown.items():
            with self.subTest(refused_row=name):
                with self.assertRaises(store.UnknownShape):
                    load(variant(fields, edit))
        with self.assertRaises(store.Mismatch):
            load(variant(fields, lambda f: f['verification'].update(refused=False)))
        with self.assertRaises(TypeError):
            store.refused_row({'refused': True, 'reason': 'x', 'stage': 'json'}, encounter_id=ENCOUNTER,
                              revision_id=REVISION, provider_run_id=RUN, text_sha256=TEXT_SHA256,
                              request_sha256=REQUEST_SHA256, response_sha256=RESPONSE_SHA256)

    def test_each_stage_can_be_stored(self):
        for stage in read.STAGES:
            with self.subTest(stage=stage):
                refused = read.refuse(stage, 'a synthetic reason')
                fields = store.refused_row(refused, encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN,
                                           text_sha256=TEXT_SHA256, request_sha256=REQUEST_SHA256,
                                           response_sha256=RESPONSE_SHA256)
                self.assertEqual(load(fields).refusal, refused)


class CopyTests(SimpleTestCase):
    def test_what_load_gives_shares_nothing_with_the_row(self):
        fields = read_row()
        before = json.dumps(fields, sort_keys=True)
        loaded = load(fields)
        loaded.events['events'].clear()
        loaded.encounter_facts['derived'].clear()
        loaded.open_questions.clear()
        loaded.verification['problems'].append('changed')
        self.assertEqual(json.dumps(fields, sort_keys=True), before)
        self.assertEqual(len(load(fields).events['events']), 4)


class DatabaseRoundTripTests(TestCase):
    """A row written to PostgreSQL (jsonb) and read back keeps its sha256 and its content, bound to its revision text
    and to its run's stored response bytes; the test database is this run's own."""

    def test_rows_written_and_read_back_keep_their_hash(self):
        workspace = f.workspace()
        member = f.member(workspace)
        encounter = f.encounter(workspace, member)
        revision = SourceRevision.objects.get(pk=f.pasted_revision(encounter, member, P1 + '\n' + P2).pk)
        runs = []
        for number in range(2):
            response = f'{{"synthetic": "response bytes {number}"}}'.encode()
            runs.append(ProviderRun.objects.create(
                encounter=encounter, revision=revision, provider=PROVIDER, adapter_version=ADAPTER_VERSION,
                request_sha256=REQUEST_SHA256, request_body={}, contexts=[], state=ProviderRun.SUCCEEDED,
                purpose=PURPOSE, response_bytes=response, response_sha256=hashlib.sha256(response).hexdigest()))
        bound = {'encounter_id': encounter.pk, 'revision_id': revision.pk, 'text_sha256': revision.text_sha256,
                 'request_sha256': REQUEST_SHA256}
        written = [store.row(provider_run_id=runs[0].pk, response_sha256=runs[0].response_sha256, **bound, **content()),
                   store.refused_row(refusal(), provider_run_id=runs[1].pk, response_sha256=runs[1].response_sha256,
                                     **bound)]
        for fields in written:
            EventInventory.objects.create(**fields)
        for fields in written:
            with self.subTest(state=fields['state']):
                stored = EventInventory.objects.get(sha256=fields['sha256'])
                response = bytes(ProviderRun.objects.get(pk=stored.provider_run_id).response_bytes)
                loaded = store.load(store.fields_of(stored), text_sha256=revision.text_sha256,
                                    response_sha256=hashlib.sha256(response).hexdigest())
                self.assertEqual((loaded.sha256, loaded.state, loaded.revision_id),
                                 (fields['sha256'], fields['state'], str(revision.pk)))
                if loaded.refused:
                    self.assertEqual(loaded.refusal, refusal())
                else:
                    self.assertEqual(loaded.events, content()['events'])
                    self.assertEqual(loaded.encounter_facts, content()['encounter_facts'])
                with self.assertRaises(store.Mismatch):  # bound to that run's bytes, not another's
                    store.load(store.fields_of(stored), text_sha256=revision.text_sha256,
                               response_sha256=hashlib.sha256(response + b' ').hexdigest())
