import copy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest import mock
import urllib.error

from ops import offsite_account_audit as audit


def ticket(at):
    return {'version': 1, 'kind': 'quillmd-account-audit-reservation', 'ticket_id': 'a'*32,
            'account_id': 'account', 'bucket_id': 'bucket', 'prefix': 'quillmd-fresh/synthetic/',
            'issued_at': at.isoformat(), 'not_before': at.isoformat(),
            'valid_until': (at + timedelta(hours=1)).isoformat(),
            'request_limit': 20, 'response_byte_limit': 8388608, 'max_run_seconds': 300,
            'reservation_reference': 'account-audit:test', 'source_revision': 'b'*40,
            'expected_policy_sha256': 'c'*64, 'collector_source_sha256': audit.digest(Path(audit.__file__).read_bytes())}


def stalled_worker(credential, ticket_bytes, connection, counters):
    counters[:] = [1, 131072, 0]
    time.sleep(30)


def stalled_result_worker(credential, ticket_bytes, connection, counters):
    # A readable pipe header is not a complete result body.
    counters[:] = [1, 131072, 0]
    os.write(connection.fileno(), struct.pack('!i', 1000))
    time.sleep(30)


class FixtureTransport:
    def __init__(self, credential, reservation, clock):
        self.requests = self.reserved_response_bytes = self.received_response_bytes = 0
        self.reservation = reservation
        self.scan_number = 0
        self.mutate = lambda name, value: value

    def authorize(self):
        self.requests += 1
        self.reserved_response_bytes += 131072
        return {'application_key_id': 'readonly-fixture', 'capabilities': ['listBuckets', 'listFiles'],
                'unrestricted_buckets': True, 'unrestricted_prefix': True, 'list_keys_performed': False}

    def request(self, name, params):
        self.requests += 1
        self.reserved_response_bytes += audit.RESPONSE_LIMITS[name] + 65536
        if name == 'b2_list_buckets':
            self.scan_number += 1
            assert params['bucketTypes'] == ['all']
            value = {'buckets': [{'bucketId': 'bucket', 'accountId': 'account', 'bucketType': 'allPrivate'}]}
        elif name == 'b2_list_file_versions':
            value = {'files': [{'fileId': 'file', 'fileName': 'quillmd-fresh/synthetic/private-name',
                     'bucketId': 'bucket', 'action': 'upload', 'contentLength': 100}],
                     'nextFileName': None, 'nextFileId': None}
        elif name == 'b2_list_unfinished_large_files':
            value = {'files': [], 'nextFileId': None}
        else:
            raise AssertionError(name)
        return self.mutate(name, value)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 9, 21, 1, tzinfo=timezone.utc)
        self.reservation = ticket(self.at)
        self.credential = {'application_key_id': 'audit-fixture', 'application_key': 'never-print-secret'}
        self.ticks = 0
        self.transport = None

    def clock(self):
        self.ticks += 1
        return self.at + timedelta(milliseconds=self.ticks)

    def run_collect(self, mutate=None):
        def factory(credential, reservation, clock):
            self.transport = FixtureTransport(credential, reservation, clock)
            if mutate:
                self.transport.mutate = mutate
            return self.transport
        return audit.collect(self.credential, audit.encoded(self.reservation), transport_factory=factory, clock=self.clock)

    def test_complete_two_scans_without_names_or_secrets(self):
        result = self.run_collect()
        self.assertEqual(result['status'], 'verified_over_observed_interval')
        self.assertEqual(result['api_calls'], 7)
        self.assertEqual(result['reserved_response_bytes'], 2097152)
        self.assertEqual(result['account_total_bytes'], 100)
        self.assertEqual(result['ticket_sha256'], audit.digest(audit.encoded(self.reservation)))
        self.assertEqual(result['scans'][0]['buckets'], result['scans'][1]['buckets'])
        self.assertTrue(result['audit_key_revocation_pending'])
        self.assertFalse(result['unused_reservation_refunded'])
        text = json.dumps(result)
        self.assertNotIn('private-name', text)
        self.assertNotIn('never-print-secret', text)
        checked = audit.validate_result(result, self.reservation, self.at + timedelta(minutes=1))
        self.assertEqual(checked['account_total_bytes'], 100)
        self.assertEqual(checked['observed_at'], result['scans'][-1]['completed_at'])

    def test_import_validation_rejects_changed_totals_times_scope_and_allowance(self):
        original = self.run_collect()
        for choice in ('total', 'time', 'scope', 'allowance', 'credential', 'incomplete', 'version'):
            value = copy.deepcopy(original)
            if choice == 'total': value['account_total_bytes'] += 1
            if choice == 'time': value['scans'][1]['completed_at'] = self.at.isoformat()
            if choice == 'scope': value['bucket_id'] = 'other'
            if choice == 'allowance': value['api_calls'] = 21
            if choice == 'credential': value['audit_credential']['capabilities'].append('writeFiles')
            if choice == 'incomplete': value['scans'][0]['complete_account_total'] = False
            if choice == 'version': value['version'] = True
            with self.subTest(choice=choice), self.assertRaises(audit.Refusal):
                audit.validate_result(value, self.reservation, self.at + timedelta(minutes=1))

    def test_import_refuses_all_unfinished_uploads_without_discarding_their_bytes(self):
        value = self.run_collect()
        for observation in value['scans']:
            observation['buckets'][0].update(unfinished_uploads=1, unfinished_part_bytes=17,
                                              quillmd_scope_bytes=117)
            observation.update(account_total_bytes=117, quillmd_scope_bytes=117, unfinished_part_bytes=17)
        value.update(account_total_bytes=117, quillmd_scope_bytes=117)
        with self.assertRaises(audit.Refusal) as raised:
            audit.validate_result(value, self.reservation, self.at + timedelta(minutes=1))
        self.assertEqual(raised.exception.code, 'unfinished_uploads')
        checked = audit.validate_result(value, self.reservation, self.at + timedelta(minutes=1), for_policy=False)
        self.assertEqual(checked['unfinished_part_bytes'], 17)
        self.assertEqual(checked['account_total_bytes'], 117)

    def test_missing_pagination_terminator_does_not_publish_partial_inventory(self):
        def mutate(name, value):
            if name == 'b2_list_file_versions':
                value.pop('nextFileId')
            return value
        result = self.run_collect(mutate)
        self.assertEqual(result['reason_code'], 'incomplete_pagination')
        self.assertNotIn('scans', result)
        self.assertEqual(result['api_calls'], 3)

    def test_changed_second_scan_preserves_failure_not_fresh_observation(self):
        def mutate(name, value):
            if name == 'b2_list_file_versions' and self.transport.scan_number == 2:
                value['files'][0]['contentLength'] += 1
            return value
        result = self.run_collect(mutate)
        self.assertEqual(result['reason_code'], 'inventory_changed')
        self.assertNotIn('scans', result)
        self.assertNotIn('account_total_bytes', result)

    def test_duplicate_version_and_missing_target_and_wrong_private_scope_refuse(self):
        for choice in ('duplicate', 'missing', 'public', 'account'):
            def mutate(name, value):
                if name == 'b2_list_file_versions' and choice == 'duplicate':
                    value['files'].append(copy.deepcopy(value['files'][0]))
                if name == 'b2_list_buckets':
                    if choice == 'missing':
                        value['buckets'] = []
                    if choice == 'public':
                        value['buckets'][0]['bucketType'] = 'allPublic'
                    if choice == 'account':
                        value['buckets'][0]['accountId'] = 'other-account'
                return value
            with self.subTest(choice=choice):
                self.assertEqual(self.run_collect(mutate)['status'], 'failed')

    def test_cursor_cycle_is_refused(self):
        def mutate(name, value):
            if name == 'b2_list_file_versions':
                value.update(files=[], nextFileName='same', nextFileId='same')
            return value
        result = self.run_collect(mutate)
        self.assertEqual(result['reason_code'], 'incomplete_pagination')
        self.assertEqual(result['api_calls'], 4)

    def test_unfinished_parts_refuse_without_write_capability_or_parts_request(self):
        transport = FixtureTransport(self.credential, self.reservation, self.clock)
        original = transport.request
        def request(name, params):
            self.assertNotEqual(name, 'b2_list_parts')
            value = original(name, params)
            if name == 'b2_list_unfinished_large_files':
                value['files'] = [{'fileId': 'unfinished', 'fileName': 'quillmd-fresh/synthetic/private-name2',
                                   'bucketId': 'bucket', 'action': 'start'}]
            return value
        transport.request = request
        with self.assertRaises(audit.Refusal) as raised:
            audit.scan(transport, self.reservation, self.clock)
        self.assertEqual(raised.exception.code, 'unfinished_parts_unmeasurable_read_only')

    def test_ticket_wrong_day_expired_future_wrong_types_refuse_before_network(self):
        changes = [{'valid_until': self.at.isoformat()}, {'not_before': (self.at+timedelta(hours=1)).isoformat()},
                   {'valid_until': (self.at+timedelta(days=1)).isoformat()}, {'request_limit': True},
                   {'response_byte_limit': 100}, {'source_revision': 'unknown'}, {'ticket_id': '../bad'}]
        for update in changes:
            with self.subTest(update=update):
                value = dict(self.reservation, **update)
                with self.assertRaises(audit.Refusal):
                    audit.validate_ticket(value, self.at)

    def test_ticket_requires_shutdown_margin_before_midnight(self):
        end = self.at.replace(hour=0) + timedelta(days=1)
        value = dict(self.reservation, valid_until=end.isoformat())
        with self.assertRaises(audit.Refusal):
            audit.validate_ticket(value, end-timedelta(seconds=300))
        audit.validate_ticket(value, end-timedelta(seconds=305))

    def test_spend_registry_refuses_copied_ticket_and_concurrent_consumer(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)/'spend'
            with mock.patch.object(audit, 'SPEND_ROOT', directory):
                audit.spend_ticket(self.reservation, b'original intent')
                with self.assertRaises(FileExistsError):
                    audit.spend_ticket(copy.deepcopy(self.reservation), b'second intent')
                self.assertEqual((directory/(self.reservation['ticket_id']+'.used.json')).read_bytes(), b'original intent')

    def test_watchdog_stops_a_blocked_request_with_reserved_attempt_preserved(self):
        at = audit.now()
        # Avoid approaching midnight during this fixture; it has no network.
        value = ticket(at.replace(hour=0, minute=0, second=0, microsecond=0))
        value.update(valid_until=(at+timedelta(seconds=10)).isoformat(), max_run_seconds=1)
        started = time.monotonic()
        result = audit.collect_bounded(self.credential, audit.encoded(value), worker=stalled_worker)
        self.assertLess(time.monotonic()-started, 5)
        self.assertEqual(result['reason_code'], 'timeout')
        self.assertEqual(result['api_calls'], 1)
        self.assertEqual(result['reserved_response_bytes'], 131072)
        self.assertNotIn('scans', result)

    @unittest.skipUnless(os.name == 'posix', 'Raw framed-pipe counterexample uses a POSIX file descriptor.')
    def test_watchdog_stops_partial_result_frame(self):
        at = audit.now()
        value = ticket(at.replace(hour=0, minute=0, second=0, microsecond=0))
        value.update(valid_until=(at+timedelta(seconds=10)).isoformat(), max_run_seconds=1)
        started = time.monotonic()
        result = audit.collect_bounded(self.credential, audit.encoded(value), worker=stalled_result_worker)
        self.assertLess(time.monotonic()-started, 5)
        self.assertEqual(result['reason_code'], 'timeout')
        self.assertEqual(result['api_calls'], 1)

    def test_cli_second_output_cannot_reuse_ticket(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            path = root/'ticket.json'
            path.write_bytes(audit.encoded(self.reservation))
            stream = mock.Mock(buffer=io.BytesIO(audit.encoded(self.credential)))
            with mock.patch.object(audit, 'now', self.clock), mock.patch.object(audit.sys, 'stdin', stream), \
                 mock.patch.object(audit, 'SPEND_ROOT', root/'spend'), \
                 mock.patch.object(audit, 'collect_bounded', return_value={'status': 'failed', 'api_calls': 1,
                                   'reason_code': 'authentication_refused'}) as collect:
                with mock.patch.object(audit.sys, 'argv', ['audit', '--ticket', str(path), '--output', str(root/'one'),
                                                          '--credential-stdin']):
                    self.assertEqual(audit.main(), 2)
                copied = root/'copied-ticket.json'
                copied.write_bytes(path.read_bytes())
                with mock.patch.object(audit.sys, 'argv', ['audit', '--ticket', str(copied), '--output', str(root/'two'),
                                                          '--credential-stdin']):
                    with self.assertRaises(FileExistsError):
                        audit.main()
                self.assertEqual(collect.call_count, 1)
                self.assertTrue((root/'one'/'account-audit.json').exists())


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 9, 21, 1, tzinfo=timezone.utc)
        self.ticket = ticket(self.at)
        self.transport = audit.NativeAuditTransport({'application_key_id': 'key', 'application_key': 'secret'},
                                                   self.ticket, clock=lambda: self.at)

    def response(self):
        return {'accountId': 'account', 'authorizationToken': 'token', 'apiInfo': {'storageApi': {
                'apiUrl': 'https://api004.backblazeb2.com', 'allowed': {'buckets': None, 'namePrefix': None,
                'capabilities': ['listBuckets', 'listFiles']}}}}

    def test_restricted_worker_wrong_account_mutation_or_groups_are_refused(self):
        for change in ('restricted_bucket', 'restricted_prefix', 'mutator', 'account', 'groups'):
            value = self.response()
            allowed = value['apiInfo']['storageApi']['allowed']
            if change == 'restricted_bucket': allowed['buckets'] = [{'id': 'bucket', 'name': 'bucket'}]
            if change == 'restricted_prefix': allowed['namePrefix'] = 'quillmd-fresh/synthetic/'
            if change == 'mutator': allowed['capabilities'].append('writeFiles')
            if change == 'account': value['accountId'] = 'other'
            if change == 'groups': value['apiInfo']['groupsApi'] = {'capabilities': ['all']}
            with self.subTest(change=change), mock.patch.object(self.transport, 'request', return_value=value):
                with self.assertRaises(audit.Refusal) as raised:
                    self.transport.authorize()
                self.assertEqual(raised.exception.code, 'scope_refused')

    def test_authentication_failure_keeps_attempt_debit(self):
        error = urllib.error.HTTPError('https://api.backblazeb2.com', 401, 'secret-provider-detail', {}, None)
        with mock.patch.object(self.transport.opener, 'open', side_effect=error):
            with self.assertRaises(audit.Refusal) as raised:
                self.transport.authorize()
        self.assertEqual(raised.exception.code, 'authentication_refused')
        self.assertEqual(self.transport.requests, 1)
        self.assertEqual(self.transport.reserved_response_bytes, 131072)

    def test_reservation_exhaustion_and_deadline_refuse_before_http(self):
        self.transport.reserved_response_bytes = self.ticket['response_byte_limit']
        with mock.patch.object(self.transport.opener, 'open') as opened:
            with self.assertRaises(audit.Refusal) as raised:
                self.transport.authorize()
            self.assertEqual(raised.exception.code, 'reservation_exhausted')
            opened.assert_not_called()
        self.transport.reserved_response_bytes = 0
        self.transport.deadline = 0
        with self.assertRaises(audit.Refusal) as raised:
            self.transport.authorize()
        self.assertEqual(raised.exception.code, 'timeout')


if __name__ == '__main__':
    unittest.main()
