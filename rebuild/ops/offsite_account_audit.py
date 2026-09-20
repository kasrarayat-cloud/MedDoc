#!/usr/bin/env python3
"""Portable, explicitly budgeted account metadata collection; never installs policy.

Run only with a VPS-issued, already charged reservation ticket and a separate
account-wide read-only audit credential. The backup worker credential is not a
fallback. Collection failure consumes its reservation and preserves old evidence.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import queue
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

TICKET_FIELDS = {'version', 'kind', 'ticket_id', 'account_id', 'bucket_id', 'prefix',
                 'issued_at', 'not_before', 'valid_until', 'request_limit',
                 'response_byte_limit', 'max_run_seconds', 'reservation_reference',
                 'source_revision', 'expected_policy_sha256', 'collector_source_sha256'}
SPEND_ROOT = Path.home() / '.quillmd-account-audit-spend'
SHUTDOWN_GRACE_SECONDS = 5
READ_ONLY = {'listBuckets', 'listFiles', 'readFiles', 'shareFiles', 'readBuckets',
             'readBucketEncryption', 'readBucketLifecycleRules', 'readFileLegalHolds',
             'readBucketRetentions', 'readBucketReplications', 'readBucketNotifications',
             'readBucketLogging', 'readFileRetentions'}
ENDPOINTS = {'b2_list_buckets', 'b2_list_file_versions', 'b2_list_unfinished_large_files'}
RESPONSE_LIMITS = {'b2_authorize_account': 65536, 'b2_list_buckets': 131072,
                   'b2_list_file_versions': 524288,
                   'b2_list_unfinished_large_files': 131072}


class Refusal(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code='inventory_invalid'):
    if not condition:
        raise Refusal(code)


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, 'ticket_invalid')
    return parsed.astimezone(timezone.utc)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def validate_ticket(ticket, at):
    require(type(ticket) is dict and set(ticket) == TICKET_FIELDS
            and type(ticket['version']) is int and ticket['version'] == 1
            and ticket['kind'] == 'quillmd-account-audit-reservation',
            'ticket_invalid')
    for name in ('ticket_id', 'account_id', 'bucket_id', 'reservation_reference'):
        require(isinstance(ticket[name], str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', ticket[name]),
                'ticket_invalid')
    require(re.fullmatch('[a-f0-9]{32}', ticket['ticket_id']), 'ticket_invalid')
    require(ticket['prefix'] == 'quillmd-fresh/synthetic/', 'ticket_invalid')
    require(isinstance(ticket['source_revision'], str) and re.fullmatch('[a-f0-9]{40}', ticket['source_revision'])
            and isinstance(ticket['expected_policy_sha256'], str)
            and re.fullmatch('[a-f0-9]{64}', ticket['expected_policy_sha256'])
            and isinstance(ticket['collector_source_sha256'], str)
            and re.fullmatch('[a-f0-9]{64}', ticket['collector_source_sha256']), 'ticket_invalid')
    issued, start, end = (stamp(ticket[name]) for name in ('issued_at', 'not_before', 'valid_until'))
    require(issued <= start <= at < end and end - start <= timedelta(hours=24)
            and start.date() == (end - timedelta(microseconds=1)).date(), 'ticket_expired')
    for name, low, high in (('request_limit', 7, 64), ('response_byte_limit', 2097152, 16777216),
                            ('max_run_seconds', 1, 300)):
        require(type(ticket[name]) is int and low <= ticket[name] <= high, 'ticket_invalid')
    require(at + timedelta(seconds=ticket['max_run_seconds'] + SHUTDOWN_GRACE_SECONDS) <= end,
            'ticket_expired')
    return ticket


def safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname is not None
            and (parsed.hostname.endswith('.backblazeb2.com') or parsed.hostname.endswith('.backblaze.com'))
            and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
            and not parsed.fragment and not parsed.query, 'scope_refused')
    return url.rstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal('redirect_refused')


class NativeAuditTransport:
    """No retry, proxy, object-content endpoint, mutation endpoint or implicit key."""
    def __init__(self, credential, ticket, clock=now, monotonic=time.monotonic, progress=None):
        require(type(credential) is dict and set(credential) == {'application_key_id', 'application_key'},
                'credential_invalid')
        require(all(isinstance(value, str) and 1 <= len(value) <= 8192 for value in credential.values()),
                'credential_invalid')
        self.credential, self.ticket, self.clock, self.monotonic = credential, ticket, clock, monotonic
        validate_ticket(ticket, clock())
        self.deadline = monotonic() + ticket['max_run_seconds']
        self.requests = self.reserved_response_bytes = self.received_response_bytes = 0
        self.progress = progress or (lambda *values: None)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.api = self.token = None

    def check_deadline(self):
        require(self.monotonic() < self.deadline and self.clock() < stamp(self.ticket['valid_until']), 'timeout')

    def request(self, name, params=None):
        self.check_deadline()
        require(name in RESPONSE_LIMITS, 'endpoint_refused')
        limit = RESPONSE_LIMITS[name]
        reservation = limit + 65536
        require(self.requests + 1 <= self.ticket['request_limit']
                and self.reserved_response_bytes + reservation <= self.ticket['response_byte_limit'],
                'reservation_exhausted')
        # The entire ticket is already debited on the VPS. Retain every attempted
        # response reservation, including timeouts and a failed request setup.
        self.requests += 1
        self.reserved_response_bytes += reservation
        self.progress(self.requests, self.reserved_response_bytes, self.received_response_bytes)
        if name == 'b2_authorize_account':
            require(params is None and self.requests == 1, 'endpoint_refused')
            url = 'https://api.backblazeb2.com/b2api/v4/b2_authorize_account'
            value = self.credential['application_key_id'] + ':' + self.credential['application_key']
            headers = {'Authorization': 'Basic ' + base64.b64encode(value.encode()).decode()}
            request = urllib.request.Request(url, headers=headers, method='GET')
        else:
            require(name in ENDPOINTS and self.api is not None and self.token is not None, 'endpoint_refused')
            request = urllib.request.Request(safe_url(self.api) + '/b2api/v4/' + name,
                      data=encoded(params), headers={'Authorization': self.token, 'Content-Type': 'application/json'},
                      method='POST')
        try:
            timeout = max(0.1, min(30, self.deadline - self.monotonic()))
            with self.opener.open(request, timeout=timeout) as response:
                require(response.status == 200, 'authentication_refused' if response.status in (401, 403) else 'transport_failed')
                body = bytearray()
                while True:
                    self.check_deadline()
                    chunk = response.read(65536)
                    self.received_response_bytes += len(chunk)
                    self.progress(self.requests, self.reserved_response_bytes, self.received_response_bytes)
                    body.extend(chunk)
                    require(len(body) <= limit, 'response_too_large')
                    if not chunk:
                        break
                self.check_deadline()
                return json.loads(body)
        except urllib.error.HTTPError as error:
            raise Refusal('authentication_refused' if error.code in (401, 403) else 'transport_failed') from None
        except (TimeoutError, socket.timeout):
            raise Refusal('timeout') from None
        except Refusal:
            raise
        except Exception:
            raise Refusal('transport_failed') from None

    def authorize(self):
        value = self.request('b2_authorize_account')
        require(value.get('accountId') == self.ticket['account_id'], 'scope_refused')
        storage = value.get('apiInfo', {}).get('storageApi', {})
        allowed = storage.get('allowed', {})
        capabilities = allowed.get('capabilities')
        require({'buckets', 'namePrefix', 'capabilities'} <= set(allowed)
                and type(capabilities) is list and all(isinstance(item, str) for item in capabilities)
                and {'listBuckets', 'listFiles'} <= set(capabilities) <= READ_ONLY
                and len(set(capabilities)) == len(capabilities), 'scope_refused')
        require(allowed.get('buckets') is None and allowed.get('bucketId') is None
                and allowed.get('bucketName') is None and allowed.get('namePrefix') in (None, ''), 'scope_refused')
        require(not value.get('apiInfo', {}).get('groupsApi', {}).get('capabilities'), 'scope_refused')
        self.api = safe_url(storage.get('apiUrl', ''))
        self.token = value.get('authorizationToken')
        require(isinstance(self.token, str) and 1 <= len(self.token) <= 8192, 'scope_refused')
        return {'application_key_id': self.credential['application_key_id'],
                'capabilities': sorted(capabilities), 'unrestricted_buckets': True,
                'unrestricted_prefix': True, 'list_keys_performed': False}


def nonnegative(value):
    require(type(value) is int and value >= 0)
    return value


def scan(transport, ticket, clock=now):
    result = {'started_at': clock().isoformat(), 'buckets': []}
    raw = transport.request('b2_list_buckets', {'accountId': ticket['account_id'], 'bucketTypes': ['all']})
    buckets = raw.get('buckets')
    require(type(buckets) is list and 1 <= len(buckets) <= 100)
    seen_buckets = set()
    for bucket in sorted(buckets, key=lambda item: str(item.get('bucketId'))):
        bucket_id = bucket.get('bucketId')
        require(isinstance(bucket_id, str) and bucket_id and bucket_id not in seen_buckets
                and bucket.get('accountId') == ticket['account_id'] and isinstance(bucket.get('bucketType'), str))
        seen_buckets.add(bucket_id)
        target = bucket_id == ticket['bucket_id']
        require(not target or bucket['bucketType'] == 'allPrivate', 'scope_refused')
        versions, seen_versions, cursor, cursors = [], set(), {}, set()
        while True:
            page = transport.request('b2_list_file_versions', {'bucketId': bucket_id, 'maxFileCount': 1000, **cursor})
            require(type(page.get('files')) is list and len(page['files']) <= 1000)
            for item in page['files']:
                identity, name, action = item.get('fileId'), item.get('fileName'), item.get('action')
                require(isinstance(identity, str) and identity and identity not in seen_versions
                        and isinstance(name, str) and name and item.get('bucketId') == bucket_id
                        and action in ('upload', 'hide', 'start'))
                size = nonnegative(item.get('contentLength'))
                require(action != 'start', 'unfinished_parts_unmeasurable_read_only')
                require(action == 'upload' or size == 0)
                seen_versions.add(identity)
                versions.append((identity, name, action, size))
            require('nextFileName' in page and 'nextFileId' in page, 'incomplete_pagination')
            continuation = (page['nextFileName'], page['nextFileId'])
            if continuation == (None, None):
                break
            require(all(isinstance(value, str) and value for value in continuation)
                    and continuation not in cursors, 'incomplete_pagination')
            cursors.add(continuation)
            cursor = dict(zip(('startFileName', 'startFileId'), continuation))
        unfinished, cursor, cursors, seen_unfinished = [], {}, set(), set()
        while True:
            page = transport.request('b2_list_unfinished_large_files', {'bucketId': bucket_id, 'maxFileCount': 100, **cursor})
            require(type(page.get('files')) is list and len(page['files']) <= 100)
            # list_parts requires writeFiles. The separate audit identity must
            # remain read-only; any unfinished upload therefore refuses a new
            # complete observation instead of claiming unmeasured parts are zero.
            require(not page['files'], 'unfinished_parts_unmeasurable_read_only')
            require('nextFileId' in page, 'incomplete_pagination')
            continuation = page['nextFileId']
            if continuation is None:
                break
            require(isinstance(continuation, str) and continuation and continuation not in cursors, 'incomplete_pagination')
            cursors.add(continuation)
            cursor = {'startFileId': continuation}
        completed = sum(row[3] for row in versions if row[2] == 'upload')
        scope_completed = sum(row[3] for row in versions if target and row[2] == 'upload' and row[1].startswith(ticket['prefix']))
        part_bytes = sum(part[1] for row in unfinished for part in row[2])
        scope_parts = sum(part[1] for row in unfinished if target and row[1].startswith(ticket['prefix']) for part in row[2])
        result['buckets'].append({'bucket_id': bucket_id, 'bucket_type': bucket['bucketType'],
                 'is_quillmd_bucket': target, 'retained_upload_versions': sum(row[2] == 'upload' for row in versions),
                 'retained_version_bytes': completed, 'quillmd_scope_bytes': scope_completed + scope_parts,
                 'version_start_markers': sum(row[2] == 'start' for row in versions),
                 'hide_markers': sum(row[2] == 'hide' for row in versions),
                 'unfinished_uploads': len(unfinished), 'unfinished_part_bytes': part_bytes,
                 'inventory_sha256': digest(encoded({'versions': sorted(versions), 'unfinished': sorted(unfinished)}))})
    require(ticket['bucket_id'] in seen_buckets, 'scope_refused')
    result.update(completed_at=clock().isoformat(), complete_account_total=True,
                  completed_version_bytes=sum(row['retained_version_bytes'] for row in result['buckets']),
                  unfinished_part_bytes=sum(row['unfinished_part_bytes'] for row in result['buckets']),
                  quillmd_scope_bytes=sum(row['quillmd_scope_bytes'] for row in result['buckets']))
    result['account_total_bytes'] = result['completed_version_bytes'] + result['unfinished_part_bytes']
    return result


def collect(credential, ticket_bytes, *, transport_factory=NativeAuditTransport, clock=now):
    """A failure result never contains a replacement observation or credential value."""
    result = {'version': 1, 'kind': 'quillmd-account-audit', 'started_at': clock().isoformat(),
              'status': 'failed', 'provider_mutations': 0, 'object_content_downloads': 0,
              'future_budget_guarantee': False, 'key_inventory_complete': False,
              'ticket_sha256': digest(ticket_bytes), 'source': 'portable_read_only_account_collector',
              'collector_source_sha256': digest(Path(__file__).read_bytes())}
    transport = None
    try:
        ticket = validate_ticket(json.loads(ticket_bytes), clock())
        require(ticket['collector_source_sha256'] == digest(Path(__file__).read_bytes()), 'collector_source_mismatch')
        result.update(ticket_id=ticket['ticket_id'], reservation_reference=ticket['reservation_reference'],
                      account_id=ticket['account_id'], bucket_id=ticket['bucket_id'], prefix=ticket['prefix'])
        transport = transport_factory(credential, ticket, clock=clock)
        metadata = transport.authorize()
        scans = [scan(transport, ticket, clock), scan(transport, ticket, clock)]
        require(scans[0]['buckets'] == scans[1]['buckets'], 'inventory_changed')
        require(stamp(scans[0]['started_at']) < stamp(scans[0]['completed_at'])
                <= stamp(scans[1]['started_at']) < stamp(scans[1]['completed_at']), 'clock_invalid')
        require(stamp(scans[1]['completed_at']) < stamp(ticket['valid_until']), 'ticket_expired')
        result.update(status='verified_over_observed_interval', audit_credential=metadata,
                      stable_over_two_scans=True, complete_account_total=True, scans=scans,
                      account_total_bytes=scans[-1]['account_total_bytes'],
                      quillmd_scope_bytes=scans[-1]['quillmd_scope_bytes'],
                      audit_key_revocation_pending=True)
    except Refusal as error:
        result['reason_code'] = error.code
    except Exception:
        result['reason_code'] = 'collector_failed'
    finally:
        result['completed_at'] = clock().isoformat()
        result['api_calls'] = getattr(transport, 'requests', 0)
        result['reserved_response_bytes'] = getattr(transport, 'reserved_response_bytes', 0)
        result['received_response_bytes'] = getattr(transport, 'received_response_bytes', 0)
        result['unused_reservation_refunded'] = False
    return result


def validate_result(value, ticket, at, *, for_policy=True):
    """Validate evidence semantics; this does not authenticate desktop reporting.

    The importer must separately match the exact ticket byte hash to its issued
    protected ticket and the charged shared-ledger entry. Observation freshness
    comes from scans, never the receipt/import time passed as ``at``.
    """
    require(type(value) is dict and type(value.get('version')) is int and value['version'] == 1
            and value.get('kind') == 'quillmd-account-audit'
            and value.get('status') == 'verified_over_observed_interval'
            and value.get('source') == 'portable_read_only_account_collector'
            and value.get('collector_source_sha256') == ticket['collector_source_sha256'])
    started, finished = stamp(value['started_at']), stamp(value['completed_at'])
    validate_ticket(ticket, started)
    require(started < finished <= at and finished < stamp(ticket['valid_until'])
            and finished - started <= timedelta(seconds=ticket['max_run_seconds']))
    require(value.get('ticket_id') == ticket['ticket_id']
            and value.get('reservation_reference') == ticket['reservation_reference']
            and value.get('account_id') == ticket['account_id']
            and value.get('bucket_id') == ticket['bucket_id'] and value.get('prefix') == ticket['prefix']
            and isinstance(value.get('ticket_sha256'), str) and re.fullmatch('[a-f0-9]{64}', value['ticket_sha256']))
    require(value.get('provider_mutations') == 0 and type(value.get('provider_mutations')) is int
            and value.get('object_content_downloads') == 0 and type(value.get('object_content_downloads')) is int
            and value.get('future_budget_guarantee') is False and value.get('key_inventory_complete') is False
            and value.get('unused_reservation_refunded') is False
            and value.get('stable_over_two_scans') is True and value.get('complete_account_total') is True)
    credential = value.get('audit_credential', {})
    capabilities = credential.get('capabilities')
    require(type(capabilities) is list and all(isinstance(item, str) for item in capabilities)
            and {'listBuckets', 'listFiles'} <= set(capabilities) <= READ_ONLY
            and len(set(capabilities)) == len(capabilities)
            and credential.get('unrestricted_buckets') is True and credential.get('unrestricted_prefix') is True
            and credential.get('list_keys_performed') is False
            and isinstance(credential.get('application_key_id'), str) and credential['application_key_id'])
    calls, reserved, received = (nonnegative(value.get(name)) for name in
                               ('api_calls', 'reserved_response_bytes', 'received_response_bytes'))
    require(7 <= calls <= ticket['request_limit'] and 131072*calls <= reserved <= ticket['response_byte_limit']
            and received <= reserved)
    scans = value.get('scans')
    require(type(scans) is list and len(scans) == 2 and scans[0]['buckets'] == scans[1]['buckets'])
    previous_end = started
    for observation in scans:
        start, end = stamp(observation['started_at']), stamp(observation['completed_at'])
        require(previous_end <= start < end <= finished and observation.get('complete_account_total') is True)
        previous_end = end
        buckets = observation.get('buckets')
        require(type(buckets) is list and 1 <= len(buckets) <= 100)
        ids, total, scope, unfinished_bytes, unfinished_count, retained_count = set(), 0, 0, 0, 0, 0
        for bucket in buckets:
            identity = bucket.get('bucket_id')
            require(isinstance(identity, str) and identity and identity not in ids
                    and type(bucket.get('is_quillmd_bucket')) is bool
                    and bucket['is_quillmd_bucket'] == (identity == ticket['bucket_id'])
                    and isinstance(bucket.get('bucket_type'), str) and bucket['bucket_type'])
            ids.add(identity)
            if bucket['is_quillmd_bucket']:
                require(bucket['bucket_type'] == 'allPrivate', 'scope_refused')
            values = {name: nonnegative(bucket.get(name)) for name in
                      ('retained_upload_versions', 'retained_version_bytes', 'quillmd_scope_bytes',
                       'version_start_markers', 'hide_markers', 'unfinished_uploads', 'unfinished_part_bytes')}
            require(values['quillmd_scope_bytes'] <= values['retained_version_bytes'] + values['unfinished_part_bytes']
                    and (bucket['is_quillmd_bucket'] or values['quillmd_scope_bytes'] == 0)
                    and (values['unfinished_uploads'] > 0 or values['unfinished_part_bytes'] == 0)
                    and isinstance(bucket.get('inventory_sha256'), str)
                    and re.fullmatch('[a-f0-9]{64}', bucket['inventory_sha256']))
            if for_policy:
                require(values['unfinished_uploads'] == values['unfinished_part_bytes']
                        == values['version_start_markers'] == 0, 'unfinished_uploads')
            total += values['retained_version_bytes']
            scope += values['quillmd_scope_bytes']
            unfinished_bytes += values['unfinished_part_bytes']
            unfinished_count += values['unfinished_uploads']
            retained_count += values['retained_upload_versions']
        require(ticket['bucket_id'] in ids, 'scope_refused')
        require(nonnegative(observation.get('completed_version_bytes')) == total
                and nonnegative(observation.get('unfinished_part_bytes')) == unfinished_bytes
                and nonnegative(observation.get('account_total_bytes')) == total + unfinished_bytes
                and nonnegative(observation.get('quillmd_scope_bytes')) == scope)
        require(nonnegative(value.get('account_total_bytes')) == total + unfinished_bytes
                and nonnegative(value.get('quillmd_scope_bytes')) == scope)
    return {'observed_at': scans[-1]['completed_at'], 'observed_start': scans[0]['started_at'],
            'account_total_bytes': total + unfinished_bytes, 'quillmd_scope_bytes': scope,
            'non_scope_bytes': total + unfinished_bytes - scope, 'buckets': len(ids),
            'retained_versions': retained_count, 'unfinished_uploads': unfinished_count,
            'unfinished_part_bytes': unfinished_bytes,
            'scope_inventory_sha256': next(item['inventory_sha256'] for item in scans[-1]['buckets']
                                           if item['is_quillmd_bucket']),
            'api_calls': calls, 'reserved_response_bytes': reserved}


def _process_collect(credential, ticket_bytes, connection, counters):
    def progress(*values):
        counters[:] = values

    def factory(secret, ticket, clock):
        return NativeAuditTransport(secret, ticket, clock=clock, progress=progress)
    try:
        connection.send_bytes(encoded(collect(credential, ticket_bytes, transport_factory=factory)))
    finally:
        connection.close()


def collect_bounded(credential, ticket_bytes, *, context=None, worker=_process_collect):
    """A parent-owned wall deadline also stops blocked headers/slow streaming.

    Socket timeout is only an inactivity limit. No credential reaches disk or
    command arguments: a spawned child receives it through multiprocessing IPC.
    Parent records conservative attempt counters before killing timed-out work.
    """
    ticket = validate_ticket(json.loads(ticket_bytes), now())
    started = now()
    context = context or multiprocessing.get_context('spawn')
    parent, child = context.Pipe(duplex=False)
    # Never wait on a child-owned lock to enforce the parent's deadline. A
    # timeout records only a last-observed progress snapshot; the entire prepaid
    # ticket remains charged regardless of this diagnostic snapshot.
    counters = context.Array('q', [0, 0, 0], lock=False)
    process = context.Process(target=worker, args=(credential, ticket_bytes, child, counters))
    deadline = time.monotonic() + ticket['max_run_seconds']
    process.start()
    child.close()
    received = queue.Queue(maxsize=1)
    def receive():
        try:
            # Pipe readability alone does not mean its full framed message has
            # arrived. Only this daemon may block reading it; the deadline owner
            # never calls recv. JSON also avoids unpickling result content.
            received.put(json.loads(parent.recv_bytes(maxlength=1048576)))
        except Exception:
            received.put(None)
    receiver = threading.Thread(target=receive, daemon=True)
    receiver.start()
    result = None
    try:
        while time.monotonic() < deadline:
            try:
                result = received.get(timeout=min(0.1, max(0, deadline - time.monotonic())))
                break
            except queue.Empty:
                pass
        if result is None:
            result = {'version': 1, 'kind': 'quillmd-account-audit', 'status': 'failed',
                      'reason_code': 'timeout' if process.is_alive() else 'collector_failed',
                      'started_at': started.isoformat(), 'completed_at': now().isoformat(),
                      'ticket_sha256': digest(ticket_bytes), 'ticket_id': ticket['ticket_id'],
                      'reservation_reference': ticket['reservation_reference'],
                      'source': 'portable_read_only_account_collector',
                      'collector_source_sha256': digest(Path(__file__).read_bytes()),
                      'provider_mutations': 0, 'object_content_downloads': 0,
                      'future_budget_guarantee': False, 'key_inventory_complete': False,
                      'unused_reservation_refunded': False,
                      'attempt_counters_are_last_observed_before_termination': True}
            result.update(zip(('api_calls', 'reserved_response_bytes', 'received_response_bytes'), counters[:]))
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        receiver.join(timeout=0.5)
        parent.close()
        require(not process.is_alive(), 'cleanup_failed')
    return result


def write_once(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def spend_ticket(ticket, intent):
    """One designated desktop/user registry, independent of copied ticket paths.

    This prevents supported local retries, not deliberate cross-machine copies
    or an administrator removing history. The operating handoff forbids both;
    another context or retry needs another shared-ledger reservation.
    """
    SPEND_ROOT.mkdir(mode=0o700, exist_ok=True)
    require(SPEND_ROOT.resolve() == SPEND_ROOT.absolute() and SPEND_ROOT.is_dir(), 'spend_registry_invalid')
    if os.name == 'posix':
        require(SPEND_ROOT.stat().st_uid == os.getuid() and SPEND_ROOT.stat().st_mode & 0o077 == 0,
                'spend_registry_invalid')
    write_once(SPEND_ROOT / (ticket['ticket_id'] + '.used.json'), intent)
    if os.name == 'posix':
        fd = os.open(SPEND_ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticket', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New evidence directory in an existing protected parent.')
    parser.add_argument('--credential-stdin', required=True, action='store_true',
                        help='Receive the separate audit credential JSON through a secure pipe, never a command argument.')
    args = parser.parse_args()
    os.umask(0o077)
    require(args.output.parent.is_dir() and not args.output.exists(), 'output_invalid')
    require(args.output.parent.resolve() == args.output.parent.absolute(), 'output_invalid')
    if os.name == 'posix':
        require(args.output.parent.stat().st_mode & 0o077 == 0, 'output_invalid')
    # Windows callers must use their existing protected ACL directory. POSIX mode
    # bits do not establish a Windows ACL claim, and no credential is saved here.
    require(args.ticket.resolve() == args.ticket.absolute(), 'ticket_invalid')
    with args.ticket.open('rb') as source:
        ticket_bytes = source.read(16385)
    require(len(ticket_bytes) <= 16384, 'ticket_invalid')
    ticket = validate_ticket(json.loads(ticket_bytes), now())
    args.output.mkdir(mode=0o700)
    # Single-use marker is in the designated desktop/user registry, independent
    # of the original or copied ticket directory and independent of output.
    # Do not remove this marker after failure; a retry needs a new paid ticket.
    intent = encoded({'ticket_sha256': digest(ticket_bytes), 'ticket_id': ticket['ticket_id'],
                      'started_at': now().isoformat(), 'output': str(args.output.absolute())})
    spend_ticket(ticket, intent)
    write_once(args.output / 'intent.json', intent)
    credential_bytes = sys.stdin.buffer.read(16385)
    require(len(credential_bytes) <= 16384, 'credential_invalid')
    result = collect_bounded(json.loads(credential_bytes), ticket_bytes)
    write_once(args.output / 'account-audit.json', encoded(result))
    print(json.dumps({'status': result['status'], 'api_calls': result['api_calls'],
                      'artifact_sha256': digest(encoded(result)), 'reason_code': result.get('reason_code')}))
    return 0 if result['status'] == 'verified_over_observed_interval' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Account audit refused; no new policy installed. Preserve the ticket and any protected attempt evidence.')
