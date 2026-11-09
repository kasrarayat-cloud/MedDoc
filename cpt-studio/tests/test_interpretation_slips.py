"""The four trial slips, contained (Gemini migration slice S03; design/contract.md 7 and 10; design/FINAL.md 5.6; design/
ADJUDICATION.md EB1-EB4), SYNTHETIC-SLIP: hand-written gemini-events@1 answers in tests/fixtures/interpretation/synthetic/,
each reproducing a slip, each slip with its correct twin as the positive control. Every fixture is a generateContent
envelope and is read the way a recorded answer is - adapter.answer_text, read.read, normalize.normalize with slice S03's
linked steps - then stored and read back by the store. Nothing is sent.

- S1, E5: an extent for a historical examination is discarded, alone, beside the correct current reach, and when the
  examination is labelled current but its own time words carry the earlier date (EB2). The examination labelled current
  with NO time words is the adjudicated residual (EB4: measured, never patched with a passage word list) - pinned below
  as such, with the structural fact the engine reads beside it: two current examinations of one family leave that
  session unresolved (FINAL 7.8).
- S2, E15: merged target words locate nowhere; a link to the erosions by the biopsy's own words has no lexical tie; erosion
  words taken from the erosions' sentence fail the statement tie. No bundling question where the biopsy names no lesion,
  or where its own verified place (the anastomosis) cannot be compared with the removal's; where it has no verified place
  and its link is unverified (S2c), nothing sets it apart from the removed polyp, so its code gets the one bundling
  question - asked, never READY and never bundled (P3; S03 review finding 6: an unverified link's site sets nothing apart).
- S3, E13: an extent invented for a digital examination is discarded and never attached or stored.
- S4, v5: strings cut before their closing parenthesis bind, the passages are extended to the document's own ")", names
  compare equal, and nothing reads as another performer."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import adapter, normalize, read, relations, store

APP = Path(__file__).resolve().parents[1]
FIXTURES = APP / 'tests' / 'fixtures' / 'interpretation' / 'synthetic'
ENCOUNTER = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0201'
REVISION = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0202'
RUN = '6f1c3f0e-2a8b-4c55-9a51-0d6c1b7e0203'


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))


def answer_of(record: dict) -> dict:
    """The answer a fixture's envelope carries, read as a recorded answer is (adapter.answer_text, read.read)."""
    request = adapter.build_request(record['text'], (), record['kind'])
    text = adapter.answer_text(request, json.dumps(record['response']).encode('utf-8'))
    assert not isinstance(text, read.Refusal), text
    parsed = read.read(text)
    assert not isinstance(parsed, read.Refusal), parsed
    return parsed


def inventory_of(name: str) -> normalize.Inventory:
    record = fixture(name)
    return normalize.normalize(answer_of(record), record['text'])


def ev(inventory, eid: str) -> dict:
    return next(item for item in inventory.events['events'] if item['id'] == eid)


def passage(inventory, pid: str) -> dict:
    return next(item for item in inventory.events['passages'] if item['id'] == pid)


def states(inventory) -> dict:
    """Every event attribute's (state, reasons), every lesion's, and every reach's."""
    found = {}
    for item in inventory.events['events']:
        for name in ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose'):
            found[f'{item["id"]}.{name}'] = (item[name]['state'], tuple(item[name]['reasons']))
        found[f'{item["id"]}.identity'] = item['target']['identity']
    for item in inventory.events['lesions']:
        found[item['id']] = (item['state'], tuple(item['reasons']))
    for index, item in enumerate(inventory.encounter_facts['reach']):
        found[f'reach[{index}]'] = (item['state'], tuple(item['reasons']), item['attached'])
    return found


class Fixtures(SimpleTestCase):
    def test_every_fixture_is_a_synthetic_slip_or_its_twin(self):
        names = sorted(path.stem for path in FIXTURES.glob('*.json'))
        self.assertEqual(len(names), 12)
        roles = {}
        for name in names:
            record = fixture(name)
            with self.subTest(name):
                self.assertEqual(set(record), {'label', 'slip', 'role', 'name', 'about', 'kind', 'text', 'response'})
                self.assertEqual((record['label'], record['name'], record['kind']), ('SYNTHETIC-SLIP', name, 'txt'))
                self.assertIn(record['role'], ('slip', 'twin'))
                self.assertIn('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', record['text'])
                self.assertEqual(record['response']['modelVersion'], adapter.MODEL)
            roles.setdefault(record['slip'], set()).add(record['role'])
        self.assertEqual(roles, {slip: {'slip', 'twin'} for slip in ('S1', 'S2', 'S3', 'S4')})

    def test_every_fixture_normalizes_and_is_stored_and_read_back(self):
        for path in sorted(FIXTURES.glob('*.json')):
            record = fixture(path.stem)
            inventory = inventory_of(path.stem)
            fields = store.row(encounter_id=ENCOUNTER, revision_id=REVISION, provider_run_id=RUN,
                               revision_text=record['text'], text_sha256=inventory.text_sha256,
                               request_sha256='2' * 64, response_sha256='3' * 64, **inventory.content())
            loaded = store.load(json.loads(json.dumps(fields)), text_sha256=inventory.text_sha256,
                                response_sha256='3' * 64)
            with self.subTest(path.stem):
                self.assertEqual(loaded.events, inventory.events)
                self.assertEqual(loaded.encounter_facts, inventory.encounter_facts)


class S1HistoricalExtent(SimpleTestCase):
    def assert_history_reach_discarded(self, inventory):
        reach = inventory.encounter_facts['reach'][0]
        self.assertEqual((reach['event'], reach['state'], reach['attached']), ('E1', 'discarded', False))
        self.assertIn('reach_not_permitted', reach['reasons'])
        self.assertIsNone(ev(inventory, 'E1')['extent'])
        self.assertIn({'where': 'encounter.reach[0]', 'reason': 'reach_not_permitted'}, inventory.verification['discarded'])

    def assert_current_reach_verified(self, inventory, index: int):
        reach = inventory.encounter_facts['reach'][index]
        self.assertEqual((reach['event'], reach['state'], reach['attached']), ('E2', 'verified', True))
        extent = ev(inventory, 'E2')['extent']
        self.assertEqual((extent['value'], extent['state'], extent['reasons']), ('terminal_ileum', 'verified', []))

    def test_alone(self):
        inventory = inventory_of('s1-e5-earlier-reach-alone')
        self.assert_history_reach_discarded(inventory)
        self.assertIsNone(ev(inventory, 'E2')['extent'])

    def test_beside_the_current_reach(self):
        inventory = inventory_of('s1-e5-earlier-reach-beside-current')
        self.assert_history_reach_discarded(inventory)
        self.assert_current_reach_verified(inventory, 1)

    def test_labelled_current_with_its_own_time_words(self):
        inventory = inventory_of('s1-e5-mislabelled-current-with-its-time-words')
        time = ev(inventory, 'E1')['time']
        self.assertEqual((time['value'], time['state'], time['reasons']), ('current_encounter', 'unverified',
                                                                           ['date_mismatch']))
        self.assertEqual(ev(inventory, 'E1')['current'], 'unresolved')
        self.assert_history_reach_discarded(inventory)
        self.assert_current_reach_verified(inventory, 1)

    def test_the_twin_stays_verified(self):
        inventory = inventory_of('s1-twin-current-reach')
        self.assert_current_reach_verified(inventory, 0)
        self.assertEqual(ev(inventory, 'E1')['time']['state'], 'verified')
        self.assertEqual(inventory.verification['reasons'], {})

    def test_eb4_the_residual_is_gemini_reading_with_no_time_words(self):
        """EB4: an examination labelled current with NO time words is Gemini's reading; no passage guard reads its
        sentence for "2024" (EB1). Its reach is attached - the measured residual, never patched with a word list. Beside
        the correct current examination it makes a second current colonoscopy, which leaves the session unresolved for
        every rule that reads it (FINAL 7.8): the engine's structural fact, recorded here."""
        record = fixture('s1-twin-current-reach')
        answer = answer_of(record)
        answer['events'][0]['time'] = {'value': 'current_encounter', 'words': '', 'passages': []}
        answer['events'][0]['performer'] = {'value': 'documenting_team', 'words': '', 'passages': []}
        answer['encounter']['reach'].insert(0, {'event': 'E1', 'landmark': 'cecum', 'words': 'reached the cecum',
                                                'passages': ['P3'], 'completion': {'value': 'not_stated', 'words': '',
                                                                                   'passages': []}})
        answer = read.read(json.dumps(answer))
        draft = normalize.Draft(answer, record['text'])
        draft.build()
        for module, name in normalize.LINKED_STEPS:
            getattr(importlib.import_module(module), name)(draft)
        self.assertEqual(draft.events['E1']['extent']['state'], 'verified')  # the residual (EB4)
        self.assertEqual(relations.Context(draft).unresolved_sessions, frozenset({'gi.colonoscopy'}))


class S2MergedTarget(SimpleTestCase):
    def assert_snare_link_verified(self, inventory):
        target = ev(inventory, 'E3')['target']
        self.assertEqual((target['lesion'], target['identity'], target['identity_by']['reasons']), ('L2', 'verified', []))

    def assert_no_bundling_question(self, inventory):
        self.assertEqual([item for item in inventory.events['relations'] if item['type'] == 'bundling_identity'], [])

    def test_s2a_merged_words_locate_nowhere(self):
        inventory = inventory_of('s2a-merged-target-words')
        target = ev(inventory, 'E2')['target']
        self.assertEqual((target['value'], target['state'], target['lesion'], target['identity']),
                         ('anastomosis', 'unverified', '', 'none'))
        self.assertIn('words_unlocated', target['reasons'])
        self.assertIsNone(target['words'])
        self.assertNotIn('two superficial erosions', json.dumps(ev(inventory, 'E2')))  # nothing of the model's words
        self.assert_snare_link_verified(inventory)
        self.assert_no_bundling_question(inventory)

    def test_s2b_no_lexical_tie_to_the_erosions(self):
        inventory = inventory_of('s2b-link-to-the-erosions')
        target = ev(inventory, 'E2')['target']
        self.assertEqual((target['lesion'], target['identity'], target['identity_by']['reasons']),
                         ('L1', 'unresolved', ['identity_no_tie']))
        self.assertEqual((target['value'], target['state']), ('anastomosis', 'verified'))  # the site is kept
        self.assert_snare_link_verified(inventory)
        self.assert_no_bundling_question(inventory)

    def test_s2c_erosion_words_from_their_own_sentence(self):
        inventory = inventory_of('s2c-erosion-words-from-their-sentence')
        target = ev(inventory, 'E2')['target']
        self.assertEqual((target['lesion'], target['identity'], target['identity_by']['reasons']),
                         ('L1', 'unresolved', ['identity_not_in_statement']))
        self.assertEqual((target['value'], target['state'], target['reasons']),
                         ('anastomosis', 'unverified', ['landmark_missing']))  # its words name no place
        self.assert_snare_link_verified(inventory)
        # the biopsy has no verified place, and the erosions' site reaches it only through a link that failed: nothing
        # sets it apart from the removed polyp, so its code asks whether it was taken from that lesion (P3)
        self.assertEqual([(item['statement'], item['event'], item['attribute'], item['reason'])
                          for item in inventory.events['relations'] if item['type'] == 'bundling_identity'],
                         [('E3', 'E2', 'target', 'biopsy_of_removed_lesion')])

    def test_the_twin_stays_verified(self):
        inventory = inventory_of('s2-twin-correct-targets')
        target = ev(inventory, 'E2')['target']
        self.assertEqual((target['value'], target['state'], target['identity']), ('anastomosis', 'verified', 'none'))
        self.assert_snare_link_verified(inventory)
        self.assertEqual(inventory.verification['reasons'], {})
        self.assert_no_bundling_question(inventory)


class S3InventedExtent(SimpleTestCase):
    def test_a_reach_on_a_digital_examination_is_discarded_and_never_stored(self):
        inventory = inventory_of('s3-e13-reach-on-a-digital-examination')
        reach = inventory.encounter_facts['reach'][0]
        self.assertEqual((reach['event'], reach['state'], reach['attached']), ('E1', 'discarded', False))
        self.assertEqual(reach['reasons'], ['words_unlocated', 'reach_not_permitted'])
        self.assertIsNone(ev(inventory, 'E1')['extent'])
        self.assertNotIn('distal rectum', json.dumps(inventory.content()))
        extent = ev(inventory, 'E2')['extent']
        self.assertEqual((extent['value'], extent['state']), ('cecum', 'verified'))

    def test_the_twin_stays_verified(self):
        inventory = inventory_of('s3-twin-colonoscopy-reach')
        extent = ev(inventory, 'E2')['extent']
        self.assertEqual((extent['value'], extent['state']), ('cecum', 'verified'))
        self.assertIsNone(ev(inventory, 'E1')['extent'])
        self.assertEqual(inventory.verification['reasons'], {})


class S4CutStrings(SimpleTestCase):
    def test_cut_strings_bind_as_their_twin_does(self):
        cut, whole = inventory_of('s4-v5-cut-strings'), inventory_of('s4-twin-whole-strings')
        for pid in ('P2', 'P4', 'P5'):
            with self.subTest(pid):
                self.assertEqual(passage(cut, pid)['extended'], 'closing_bracket')
                self.assertEqual(passage(whole, pid)['extended'], '')
                self.assertEqual(passage(cut, pid)['spans'], passage(whole, pid)['spans'])
        self.assertEqual(states(cut), states(whole))
        names = cut.encounter_facts['documenting_endoscopist']['names']
        self.assertEqual(names, whole.encounter_facts['documenting_endoscopist']['names'])
        self.assertEqual(names, [{'tokens': ['marta', 'lindqvist'], 'titled': False, 'credentialed': True}])
        self.assertNotIn('name_mismatch', json.dumps(cut.verification))
        self.assertNotIn('name_not_other', json.dumps(cut.verification))

    def test_performers_compare_by_their_tokens(self):
        inventory = inventory_of('s4-v5-cut-strings')
        own, other = ev(inventory, 'E3')['performer'], ev(inventory, 'E1')['performer']
        self.assertEqual((own['value'], own['state'], own['reasons']), ('documenting_team', 'verified', []))
        self.assertEqual([name['tokens'] for name in own['literals']['names']], [['marta', 'lindqvist']])
        self.assertEqual((other['value'], other['state']), ('other_clinician', 'verified'))
        self.assertEqual([name['tokens'] for name in other['literals']['names']], [['tomas', 'brandt']])

    def test_the_denial_today_never_meets_the_historical_removal(self):
        inventory = inventory_of('s4-v5-cut-strings')
        found = [(item['type'], item['attribute'], item['reason']) for item in inventory.events['relations']
                 if item['statement'] == 'E4']
        self.assertEqual(found, [('independent', 'time', 'another_time')])

    def test_the_twin_stays_verified(self):
        inventory = inventory_of('s4-twin-whole-strings')
        self.assertEqual(inventory.verification['reasons'], {})
        self.assertEqual(ev(inventory, 'E3')['target']['identity'], 'verified')


class TwinsAreTheControls(SimpleTestCase):
    def test_each_slip_differs_from_its_twin_only_where_it_slips(self):
        pairs = {'s1-e5-earlier-reach-beside-current': 's1-twin-current-reach',
                 's2b-link-to-the-erosions': 's2-twin-correct-targets',
                 's3-e13-reach-on-a-digital-examination': 's3-twin-colonoscopy-reach'}
        for slip, twin in pairs.items():
            slipped, control = states(inventory_of(slip)), states(inventory_of(twin))
            changed = {key for key in set(slipped) | set(control) if slipped.get(key) != control.get(key)}
            with self.subTest(slip):
                self.assertTrue(changed)
                self.assertTrue(all(key.startswith(('reach', 'E2.target', 'E2.identity')) for key in changed), changed)


if __name__ == '__main__':  # pragma: no cover
    sys.exit('Run with manage.py test.')
