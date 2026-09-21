"""Provider-free regressions for malformed Native inventory admission, not account audits."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import automatic_offsite as auto


class InventoryCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.transport = auto.NativeTransport({'bucket_id': 'e' * 24},
            SimpleNamespace(limits={'scope_storage_ceiling_bytes': 100}))
        self.addCleanup(self.transport.close)
        self.unfinished = {'files': [], 'nextFileId': None}
        self.versions = {'files': [], 'nextFileName': None, 'nextFileId': None}
        self.expected = {auto.offsite.PREFIX + 'synthetic-object': b'x' * 99}
        # Even a mistaken test path must fail before live HTTP.
        guard = patch.object(self.transport.session, 'request', side_effect=AssertionError('No provider calls in fixture'))
        guard.start()
        self.addCleanup(guard.stop)

    def refused_without_permits(self, pages, expected_calls, code='remote_corrupt'):
        with patch.object(self.transport, 'api_call', side_effect=pages) as calls:
            with self.assertRaisesRegex(auto.Refusal, code):
                self.transport.inventory()
            self.assertEqual(calls.call_count, expected_calls)
        self.assertIsNone(self.transport._inventory)
        self.assertEqual(self.transport._write_permits, {})
        with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
            self.transport.prepare_uploads(self.expected, [])

    def test_explicit_completed_empty_inventory_still_permits_bounded_upload(self):
        with patch.object(self.transport, 'api_call', side_effect=[self.unfinished, self.versions]):
            rows = self.transport.inventory()
        self.assertEqual(rows, [])
        self.transport.prepare_uploads(self.expected, rows)
        self.assertEqual(set(self.transport._write_permits), set(self.expected))

    def test_unfinished_missing_terminator_is_unknown_before_versions_request(self):
        self.refused_without_permits([{'files': []}], 1)

    def test_either_missing_version_terminator_refuses_capacity_admission(self):
        for missing in (('nextFileName',), ('nextFileId',), ('nextFileName', 'nextFileId')):
            malformed = copy.deepcopy(self.versions)
            for field in missing:
                del malformed[field]
            with self.subTest(missing=missing):
                self.refused_without_permits([self.unfinished, malformed], 2)

    def test_nonobject_or_invalid_list_cannot_be_complete_inventory(self):
        for value in (None, [], {'files': None, 'nextFileId': None}, {'files': [], 'nextFileId': False}):
            with self.subTest(endpoint='unfinished', value=value):
                self.refused_without_permits([value], 1)
        for value in (None, [], dict(self.versions, files=None), dict(self.versions, files=[None])):
            with self.subTest(endpoint='versions', value=value):
                self.refused_without_permits([self.unfinished, value], 2)

    def test_inconsistent_empty_or_foreign_cursor_pair_cannot_complete_inventory(self):
        for name, identity in ((None, 'id'), (auto.offsite.PREFIX + 'next', None),
                               ('', 'id'), (auto.offsite.PREFIX + 'next', ''),
                               ('foreign/next', 'id'), (False, 'id'), (auto.offsite.PREFIX + 'next', False)):
            with self.subTest(name=name, identity=identity):
                page = dict(self.versions, nextFileName=name, nextFileId=identity)
                self.refused_without_permits([self.unfinished, page], 2)

    def test_multi_page_cursor_cycle_stops_without_repeated_provider_work(self):
        first = dict(self.versions, nextFileName=auto.offsite.PREFIX + 'a', nextFileId='a')
        second = dict(self.versions, nextFileName=auto.offsite.PREFIX + 'b', nextFileId='b')
        self.refused_without_permits([self.unfinished, first, second, first], 4)

    def test_failed_refresh_invalidates_previous_inventory_write_admission(self):
        with patch.object(self.transport, 'api_call', side_effect=[self.unfinished, self.versions]):
            prior = self.transport.inventory()
        self.assertIs(self.transport._inventory, prior)
        self.refused_without_permits([{'files': []}], 1)
        with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
            self.transport.prepare_uploads(self.expected, prior)

    def test_unfinished_content_or_continuation_still_refuses_capacity(self):
        for value in (dict(self.unfinished, files=[{'fileId': 'unfinished'}]),
                      dict(self.unfinished, nextFileId='more')):
            with self.subTest(value=value):
                self.refused_without_permits([value], 1, 'capacity_refused')

    def test_failed_refresh_revokes_already_issued_permits_without_allowing_reprepare(self):
        with patch.object(self.transport, 'api_call', side_effect=[self.unfinished, self.versions]):
            prior = self.transport.inventory()
        self.transport.prepare_uploads(self.expected, prior)
        self.assertEqual(set(self.transport._write_permits), set(self.expected))
        self.refused_without_permits([{'files': []}], 1)
        self.assertTrue(self.transport._uploads_prepared)
        with patch.object(self.transport, 'api_call') as api:
            name, payload = next(iter(self.expected.items()))
            with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
                self.transport.put(name, payload)
            api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
