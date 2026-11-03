"""GI round 4 harness, H1: the offline replay of the regression encounters (ops/gi4/replay.py) on the committed derived
fixtures (tests/fixtures/gi4/regression/: the synthetic texts the service read and its retained provider answers).

Pinned against installed 80df1831d168 (tests/fixtures/gi4/pins/replay.json, written from a sealed export): any movement
in any member state - the date channel, a request, routing, the inventory, a proposal's bucket, status or fingerprint, a
question, an offer - fails here until a package re-pins it beside its declaration. The positive controls: the replay is
deterministic, and three planted changes (a date answer, a routing order, the request's date line) each move it.
Offline: nothing is sent; the assess child never reads the database.
"""
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from ops.gi4 import boot, pins, regression, replay

PIN = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'pins' / 'replay.json').read_text())


class ReplayTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.docs = regression.load_fixtures()
        cls.result = replay.replay(cls.docs)

    def test_the_fixtures_are_the_texts_the_service_read(self):
        for doc_id, doc in self.docs.items():
            self.assertEqual(boot.sha256_text(doc['text']), doc['text_sha256'], doc_id)
            self.assertTrue(doc['text'].startswith('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT'), doc_id)
        self.assertEqual(sorted(self.docs), sorted(regression.ALL_DOCS))

    def test_every_retained_request_rebuilds_byte_identically(self):
        for doc_id, rec in self.result['documents'].items():
            failed = [e for e in rec['expectations'] if e['id'].startswith('request.') and not e['ok']]
            self.assertEqual(failed, [], doc_id)
            self.assertTrue(any(e['id'].startswith('request.') for e in rec['expectations']), doc_id)

    def test_the_replay_equals_installed_in_every_member_state(self):
        now = pins.compact_replay(self.result)
        diffs = boot.differences(PIN['documents'], now)
        self.assertEqual(diffs, [], 'the replay moved against installed 80df1831d168 (re-pin only with a declaration):'
                                    '\n' + '\n'.join(diffs[:40]))

    def test_the_walk_states_reuse_the_retained_answers(self):
        for doc_id, rec in self.result['documents'].items():
            walk = rec['states'].get('walk') or rec['states']['none']
            self.assertTrue(walk['response'].startswith('retained'), (doc_id, walk['response']))

    def test_every_state_is_scored_and_hard_expectations_are_safety_rules(self):
        for doc_id, rec in self.result['documents'].items():
            levels = {e['level'] for e in rec['expectations']}
            self.assertIn('HARD', levels, doc_id)
            sends = [e for e in rec['expectations'] if e['id'].startswith('date.sends-only-the-truth')]
            self.assertEqual(len(sends), len(rec['states']), doc_id)

    def test_the_member_states(self):
        states = dict(regression.member_states(self.docs['h4-01']))
        self.assertEqual(states['none'], None)
        self.assertEqual(states['walk'], '2026-10-26')
        self.assertEqual(states['far'], '1998-01-01')
        self.assertEqual((states['minus1'], states['plus1']), ('2026-10-25', '2026-10-27'))
        self.assertIn('doc:2026-11-23', states)
        self.assertEqual(len(set(states.values())), len(states))  # one state per answer


class ReplayPositiveControlTests(SimpleTestCase):
    """The replay must see a planted change: each patch below changes one reading, and the replay must differ."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.docs = {k: v for k, v in regression.load_fixtures().items() if k in ('h2-08', 'h4-04', 'h4-05')}
        cls.base = pins.compact_replay(replay.replay(cls.docs))

    def moved(self):
        return boot.differences(self.base, pins.compact_replay(replay.replay(self.docs)))

    def test_control_0_the_replay_is_deterministic(self):
        self.assertEqual(self.moved(), [])

    def test_control_1_a_member_date_conflict_no_longer_held(self):
        with mock.patch('studio.gi.context.is_member_conflict', return_value=False):
            self.assertNotEqual(self.moved(), [])

    def test_control_2_another_order_of_another_encounters_statuses(self):
        with mock.patch('studio.gi.detect.ELSEWHERE_ORDER', ('planned', 'historical', 'negated')):
            self.assertNotEqual(self.moved(), [])

    def test_control_3_another_date_line(self):
        from studio.providers import corti
        original = corti.build_coding_request

        def build(provider, adapter, text, day, limit):
            return original(provider, adapter, text + ('\n' if day else ''), day, limit)

        with mock.patch('studio.providers.corti.build_coding_request', build):
            self.assertNotEqual(self.moved(), [])
