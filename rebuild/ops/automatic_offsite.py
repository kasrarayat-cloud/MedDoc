#!/usr/bin/env python3
"""Bounded encrypted offsite recurrence. No deletion, restore, provisioning or application access."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import time
from urllib.parse import quote, urlsplit

import requests

try:
    from . import offsite_backup as offsite
except ImportError:
    import offsite_backup as offsite

backup = offsite.backup
STATE = offsite.RUNTIME / 'automatic-offsite'
POLICY = offsite.CONFIG_PARENT / 'offsite-policy.json'
BACKUPS = offsite.RUNTIME / 'new-system-backups'
KEY = offsite.CONFIG_PARENT / 'fresh-backup-current-20260917.key'
CONFIG = offsite.CONFIG_PARENT / 'b2-offsite.json'
REASONS = {'pending_configuration', 'policy_missing', 'policy_invalid', 'policy_expired', 'capacity_refused', 'budget_exhausted',
           'remote_corrupt', 'remote_uncertain', 'local_authentication_failed', 'local_backup_stale',
           'transport_failed', 'scope_refused', 'lock_busy', 'deadline', 'state_invalid'}
POLICY_FIELDS = {'version', 'approved', 'approval_reference', 'observed_at', 'valid_until', 'bucket_id', 'prefix',
                 'account_storage_limit_bytes', 'account_storage_used_bytes_at_observation',
                 'scope_storage_bytes_at_observation', 'scope_storage_ceiling_bytes',
                 'exclusive_scope_allocation_confirmed', 'exclusive_daily_budgets_confirmed',
                 'daily_download_budget_bytes', 'daily_request_budget', 'max_run_seconds', 'max_local_age_hours'}


class Refusal(RuntimeError):
    def __init__(self, code):
        assert code in REASONS
        self.code = code
        super().__init__(code)


def check(condition, code):
    if not condition:
        raise Refusal(code)


def now():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        check(result.tzinfo is not None, 'policy_invalid')
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise Refusal('policy_invalid') from None


def policy(path=POLICY, at=None):
    """Fail closed without spending a provider request; account envelope is owner evidence, not inferred."""
    path, at = Path(path).absolute(), at or now()
    check(path.parent == offsite.CONFIG_PARENT and path.resolve() == path, 'policy_invalid')
    if not path.exists():
        raise Refusal('policy_missing')
    try:
        item = json.loads(offsite.read_private(path, 16384))
        check(type(item) is dict and set(item) == POLICY_FIELDS and item['version'] == 1, 'policy_invalid')
        check(item['approved'] is True and item['exclusive_scope_allocation_confirmed'] is True
              and item['exclusive_daily_budgets_confirmed'] is True, 'policy_invalid')
        check(isinstance(item['approval_reference'], str) and 1 <= len(item['approval_reference']) <= 256
              and re.fullmatch(r'[a-f0-9]{24}', item['bucket_id']) and item['prefix'] == offsite.PREFIX,
              'policy_invalid')
        start, end = timestamp(item['observed_at']), timestamp(item['valid_until'])
        check(start <= at < end and end - start <= timedelta(days=31), 'policy_expired')
        names = ('account_storage_limit_bytes', 'account_storage_used_bytes_at_observation',
                 'scope_storage_bytes_at_observation', 'scope_storage_ceiling_bytes',
                 'daily_download_budget_bytes', 'daily_request_budget', 'max_run_seconds', 'max_local_age_hours')
        check(all(type(item[name]) is int and item[name] >= 0 for name in names), 'policy_invalid')
        check(0 < item['account_storage_limit_bytes'] <= 10_000_000_000
              and item['scope_storage_bytes_at_observation'] <= item['account_storage_used_bytes_at_observation']
              <= item['account_storage_limit_bytes'], 'policy_invalid')
        unallocated = item['account_storage_limit_bytes'] - item['account_storage_used_bytes_at_observation']
        check(0 < item['scope_storage_ceiling_bytes'] <= unallocated + item['scope_storage_bytes_at_observation']
              and 0 < item['daily_download_budget_bytes'] <= 1_000_000_000
              and 0 < item['daily_request_budget'] <= 1000
              and 30 <= item['max_run_seconds'] <= 900 and 1 <= item['max_local_age_hours'] <= 48,
              'policy_invalid')
        return item
    except Refusal:
        raise
    except Exception:
        raise Refusal('policy_invalid') from None


# Public validation alias used by the fail-closed installer.
load_policy = policy

def atomic(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        offsite.read_private(path, 4 * 1024 * 1024)
    fd, temporary = tempfile.mkstemp(prefix='.offsite-state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path, default):
    if not path.exists() and not path.is_symlink():
        return default
    try:
        item = json.loads(offsite.read_private(path, 4 * 1024 * 1024))
        check(type(item) is dict, 'state_invalid')
        return item
    except Refusal:
        raise
    except Exception:
        raise Refusal('state_invalid') from None


def stage_summary(name, value):
    """Untrusted protected state is not a logging allowlist. Only typed proof identifiers escape."""
    check(type(value) is dict, 'state_invalid')
    check(isinstance(value.get('run_id'), str) and re.fullmatch(offsite.RUN_ID, value['run_id'])
          and isinstance(value.get('manifest_cipher_sha256'), str)
          and re.fullmatch(offsite.SHA, value['manifest_cipher_sha256']), 'state_invalid')
    fields = ('table_count', 'row_count', 'file_count') if name == 'last_isolated_restore' else ('object_count', 'cipher_bytes')
    check(all(type(value.get(key)) is int and value[key] >= 0 for key in fields), 'state_invalid')
    date_field = 'completed_at' if name == 'last_remote_complete' else 'verified_at'
    try:
        date = timestamp(value[date_field]).isoformat()
    except Exception:
        raise Refusal('state_invalid') from None
    result = {key: value[key] for key in ('run_id', 'manifest_cipher_sha256', *fields)}
    result[date_field] = date
    if name == 'last_isolated_restore':
        check(value.get('source') in ('vps_key', 'independently_retrieved_key'), 'state_invalid')
        result['source'] = value['source']
    return result


def status_summary(value):
    if not value:
        return {}
    check(value.get('version') == 1 and value.get('state') in
          ('pending_configuration', 'running', 'complete', 'refused', 'failed'), 'state_invalid')
    check(value.get('reason_code') in REASONS | {None}, 'state_invalid')
    result = {'version': 1, 'state': value['state'], 'reason_code': value.get('reason_code')}
    for name in ('last_remote_complete', 'last_verified_readback', 'last_isolated_restore'):
        if name in value:
            result[name] = stage_summary(name, value[name])
    for name in ('started_at', 'finished_at'):
        if name in value:
            try:
                result[name] = timestamp(value[name]).isoformat()
            except Exception:
                raise Refusal('state_invalid') from None
    if 'automatic_enabled' in value:
        check(type(value['automatic_enabled']) is bool, 'state_invalid')
        result['automatic_enabled'] = value['automatic_enabled']
    return result


@contextmanager
def exclusion(state):
    state = backup.private_dir(state, create=True)
    try:
        fd = os.open(state / 'execution.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise Refusal('state_invalid') from None
    try:
        info = os.fstat(fd)
        check(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
              and stat.S_IMODE(info.st_mode) == 0o600, 'state_invalid')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal('lock_busy') from None
        yield
    finally:
        os.close(fd)


class Budget:
    """Every attempted HTTP request/decryption readback reserves budget durably before I/O.

    Reservations survive errors and are never refunded, since timeout does not imply no provider work.
    """
    def __init__(self, state, limits, clock=now, monotonic=time.monotonic):
        self.path, self.limits, self.clock, self.monotonic = Path(state) / 'budget.json', limits, clock, monotonic
        self.deadline = monotonic() + limits['max_run_seconds']

    def debit(self, download=0):
        check(self.monotonic() < self.deadline, 'deadline')
        check(self.clock() < timestamp(self.limits['valid_until']), 'policy_expired')
        today = self.clock().strftime('%Y-%m-%d')
        previous = read_json(self.path, {'version': 1, 'day': today, 'requests': 0, 'download_bytes': 0})
        check(set(previous) == {'version', 'day', 'requests', 'download_bytes'} and previous['version'] == 1
              and type(previous['requests']) is int and previous['requests'] >= 0
              and type(previous['download_bytes']) is int and previous['download_bytes'] >= 0
              and isinstance(previous['day'], str) and previous['day'] <= today, 'state_invalid')
        if previous['day'] != today:
            previous = {'version': 1, 'day': today, 'requests': 0, 'download_bytes': 0}
        check(previous['requests'] + 1 <= self.limits['daily_request_budget']
              and previous['download_bytes'] + download <= self.limits['daily_download_budget_bytes'],
              'budget_exhausted')
        previous['requests'] += 1
        previous['download_bytes'] += download
        atomic(self.path, previous)


def provider_url(value):
    parsed = urlsplit(value)
    check(parsed.scheme == 'https' and parsed.hostname is not None
          and (parsed.hostname.endswith('.backblazeb2.com') or parsed.hostname.endswith('.backblaze.com'))
          and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
          and not parsed.fragment, 'scope_refused')
    return value


class NativeTransport:
    """Native v4; no implicit retries, redirects, proxies, netrc, multipart or bucket discovery.

    Counts each request explicitly. Provider SHA-1 fields are not used as readback evidence.
    """
    def __init__(self, config, budget):
        self.config, self.budget = config, budget
        self.session = requests.Session()
        self.session.trust_env = False
        self.token = self.api = self.download = self.upload = self.upload_token = None

    def close(self):
        self.session.close()

    def request(self, method, url, *, limit=65536, **kwargs):
        provider_url(url)
        # Include a full bounded response chunk beyond the expected body. A corrupt oversized
        # response can be rejected after receipt; that last chunk must still have been reserved.
        self.budget.debit(limit + 65536)
        try:
            with self.session.request(method, url, timeout=(10, 30), allow_redirects=False,
                                      stream=True, **kwargs) as response:
                check(response.status_code == 200, 'transport_failed')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    check(self.budget.monotonic() < self.budget.deadline, 'deadline')
                    content.extend(chunk)
                    check(len(content) <= limit, 'remote_corrupt')
                return bytes(content)
        except Refusal:
            raise
        except Exception:
            raise Refusal('transport_failed') from None

    def api_call(self, name, params):
        return json.loads(self.request('POST', self.api + '/b2api/v4/' + name,
                         headers={'Authorization': self.token}, json=params,
                         limit=1024 * 1024 if name == 'b2_list_file_versions' else 65536))

    def authorize(self):
        response = json.loads(self.request('GET', 'https://api.backblazeb2.com/b2api/v4/b2_authorize_account',
                              auth=(self.config['application_key_id'], self.config['application_key'])))
        try:
            safe = offsite.verify_scope(self.config, response)
            storage = response['apiInfo']['storageApi']
            self.api, self.download = provider_url(storage['apiUrl']), provider_url(storage['downloadUrl'])
            self.token = response['authorizationToken']
            check(isinstance(self.token, str) and 1 <= len(self.token) <= 8192, 'scope_refused')
            return safe
        except Refusal:
            raise
        except Exception:
            raise Refusal('scope_refused') from None

    def inventory(self):
        items, cursor, seen = [], {}, set()
        for _ in range(100):
            result = self.api_call('b2_list_file_versions', {'bucketId': self.config['bucket_id'],
                                   'prefix': offsite.PREFIX, 'maxFileCount': 1000, **cursor})
            check(type(result.get('files')) is list and len(result['files']) <= 1000, 'remote_corrupt')
            for item in result['files']:
                check(item.get('bucketId') == self.config['bucket_id'] and isinstance(item.get('fileName'), str)
                      and item['fileName'].startswith(offsite.PREFIX) and isinstance(item.get('fileId'), str)
                      and item['fileId'] not in seen and type(item.get('contentLength')) is int
                      and item['contentLength'] >= 0, 'remote_corrupt')
                # Multipart parts are not measurable through list versions. Refuse all writes instead of assuming zero.
                check(item.get('action') in ('upload', 'hide'), 'capacity_refused')
                seen.add(item['fileId'])
                items.append({key: item[key] for key in ('fileName', 'fileId', 'action', 'contentLength')})
            next_name, next_id = result.get('nextFileName'), result.get('nextFileId')
            if next_name is None and next_id is None:
                return items
            check(isinstance(next_name, str) and next_name.startswith(offsite.PREFIX)
                  and isinstance(next_id, str) and (next_name, next_id) != (cursor.get('startFileName'), cursor.get('startFileId')),
                  'remote_corrupt')
            cursor = {'startFileName': next_name, 'startFileId': next_id}
        raise Refusal('budget_exhausted')

    def get(self, row, expected_size):
        check(row['contentLength'] == expected_size, 'remote_corrupt')
        return self.request('GET', self.download + '/b2api/v4/b2_download_file_by_id', limit=expected_size,
                            headers={'Authorization': self.token}, params={'fileId': row['fileId']})

    def put(self, name, payload):
        check(name.startswith(offsite.PREFIX) and len(payload) <= offsite.MAX_CIPHER, 'remote_corrupt')
        if self.upload is None:
            result = self.api_call('b2_get_upload_url', {'bucketId': self.config['bucket_id']})
            check(result.get('bucketId') == self.config['bucket_id'], 'scope_refused')
            self.upload, self.upload_token = provider_url(result['uploadUrl']), result['authorizationToken']
        result = json.loads(self.request('POST', self.upload, data=payload, headers={
            'Authorization': self.upload_token, 'X-Bz-File-Name': quote(name, safe='/'),
            'Content-Type': 'application/octet-stream', 'Content-Length': str(len(payload)),
            'X-Bz-Content-Sha1': hashlib.sha1(payload).hexdigest()}))
        check(result.get('bucketId') == self.config['bucket_id'] and result.get('fileName') == name
              and result.get('action') == 'upload' and result.get('contentLength') == len(payload)
              and isinstance(result.get('fileId'), str), 'remote_corrupt')
        return {key: result[key] for key in ('fileName', 'fileId', 'action', 'contentLength')}


def select_bundle(directory, key, limits, active, at=None):
    try:
        root = backup.private_dir(directory)
        if active.get('run_id') and not active.get('complete'):
            check(re.fullmatch(offsite.RUN_ID, active['run_id']), 'state_invalid')
            candidate = root / active['run_id']
        else:
            candidates = sorted(item for item in root.iterdir() if re.fullmatch(offsite.RUN_ID, item.name)
                                and not (item / 'INCOMPLETE').exists())
            check(bool(candidates), 'local_authentication_failed')
            candidate = candidates[-1]
        manifest, objects = offsite.authenticated_plan(candidate, key)
        captured = datetime.strptime(manifest['run_id'].split('-')[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        check(timedelta(0) <= (at or now()) - captured <= timedelta(hours=limits['max_local_age_hours']),
              'local_backup_stale')
        return manifest, objects, backup.key_at(key)
    except Refusal:
        raise
    except Exception:
        raise Refusal('local_authentication_failed') from None


def transfer(manifest, objects, cipher, transport, limits, state):
    """Resume known bytes, never blindly repeat a possible write; manifest is the remote completion record."""
    try:
        offsite.validate_bundle(manifest, objects, cipher)
    except Exception:
        raise Refusal('local_authentication_failed') from None
    run_id, digest = manifest['run_id'], backup.digest(objects['manifest.json.fernet'])
    identity = offsite.PREFIX + run_id + '/' + digest + '/'
    path = Path(state) / 'active.json'
    previous = read_json(path, {})
    if previous.get('run_id') == run_id:
        check(previous.get('manifest_cipher_sha256') == digest, 'state_invalid')
    else:
        check(not previous or previous.get('complete') is True, 'state_invalid')
        previous = {'version': 1, 'run_id': run_id, 'manifest_cipher_sha256': digest,
                    'pending': None, 'complete': False}
    inventory = transport.inventory()
    stored = sum(row['contentLength'] for row in inventory)
    by_name = {}
    for row in inventory:
        by_name.setdefault(row['fileName'], []).append(row)
    existing_names = set(by_name)
    expected = {identity + name: payload for name, payload in objects.items()}
    # A published manifest plus an absent/hidden object is corruption, never silently repaired.
    published = identity + 'manifest.json.fernet' in by_name
    if published:
        check(all(name in by_name and by_name[name][0]['action'] == 'upload' for name in expected), 'remote_corrupt')
    missing_bytes = sum(len(payload) for name, payload in expected.items() if name not in by_name)
    check(stored + missing_bytes <= limits['scope_storage_ceiling_bytes'], 'capacity_refused')
    pending = previous.get('pending')
    if pending is not None:
        check(pending in expected, 'state_invalid')
        # No object after an uncertain PUT is insufficient evidence to retry: its completion may still be in flight.
        check(pending in by_name, 'remote_uncertain')
    atomic(path, previous)
    for name in sorted(set(objects) - {'manifest.json.fernet'}) + ['manifest.json.fernet']:
        full_name, payload = identity + name, objects[name]
        if full_name in by_name:
            row = by_name[full_name][0]
            check(row['action'] == 'upload', 'remote_corrupt')
        else:
            previous['pending'] = full_name
            atomic(path, previous)  # Durable before PUT. A process crash cannot erase uncertainty.
            row = transport.put(full_name, payload)
            by_name[full_name] = [row]
        received = transport.get(row, len(payload))
        check(len(received) == len(payload) and backup.digest(received) == backup.digest(payload), 'remote_corrupt')
        # Local authenticated bytes + exact ciphertext readback prove the same authenticated plaintext, without SHA-1 assumptions.
        check(cipher.decrypt(received) == cipher.decrypt(payload), 'remote_corrupt')
        if previous.get('pending') == full_name:
            previous['pending'] = None
            atomic(path, previous)
    previous['complete'] = True
    atomic(path, previous)
    total = sum(len(value) for value in objects.values())
    return {'run_id': run_id, 'manifest_cipher_sha256': digest, 'object_count': len(objects),
            'cipher_bytes': total, 'scope_stored_bytes_before': stored,
            'scope_stored_bytes_after': stored + missing_bytes,
            'scope_ceiling_bytes': limits['scope_storage_ceiling_bytes'],
            'new_object_count': sum(name not in existing_names for name in expected),
            'ciphertext_sha256_verified': True, 'authenticated': True,
            'provider_sha1_metadata_acceptance': 'not used as verification evidence'}


def execute(*, state=STATE, policy_path=POLICY, config_path=CONFIG, key=KEY, backups=BACKUPS,
            transport_factory=NativeTransport):
    """One supervised attempt. Immutable attempts preserve failures; latest status keeps prior evidence."""
    state = backup.private_dir(state, create=True)
    attempt = now().strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
    record = {'version': 1, 'attempt': attempt, 'state': 'running', 'reason_code': None,
              'started_at': now().isoformat(), 'provider_calls_permitted': False,
              'restore_performed': False, 'independent_custody_verified': False}
    try:
        with exclusion(state):
            previous = read_json(state / 'status.json', {})
            for name in ('last_remote_complete', 'last_verified_readback', 'last_isolated_restore'):
                if name in previous:
                    record[name] = stage_summary(name, previous[name])
            atomic(state / 'status.json', record)
            transport = None
            try:
                limits = policy(policy_path)
                config = offsite.configuration(config_path)
                check(config['bucket_id'] == limits['bucket_id'], 'policy_invalid')
                active = read_json(state / 'active.json', {})
                manifest, objects, cipher = select_bundle(backups, key, limits, active)
                identity = (manifest['run_id'], backup.digest(objects['manifest.json.fernet']))
                complete = previous.get('last_remote_complete', {})
                if (active.get('complete') is True
                        and (active.get('run_id'), active.get('manifest_cipher_sha256')) == identity
                        and (complete.get('run_id'), complete.get('manifest_cipher_sha256')) == identity):
                    # A scheduler restart is not a fresh remote verification. Preserve the old proof's time.
                    record.update(state='complete', result={'no_new_local_backup': True, 'provider_calls': 0})
                else:
                    budget = Budget(state, limits)
                    transport = transport_factory(config, budget)
                    record['provider_calls_permitted'] = True
                    record['scope'] = transport.authorize()
                    result = transfer(manifest, objects, cipher, transport, limits, state)
                    finished = now().isoformat()
                    common = {name: result[name] for name in ('run_id', 'manifest_cipher_sha256', 'object_count', 'cipher_bytes')}
                    record.update(state='complete', result=result,
                                  last_remote_complete={**common, 'completed_at': finished},
                                  last_verified_readback={**common, 'verified_at': finished})
            except Refusal as error:
                record.update(state='refused', reason_code=error.code)
            except Exception:
                record.update(state='failed', reason_code='transport_failed')
            finally:
                if transport is not None:
                    transport.close()
                record['finished_at'] = now().isoformat()
                atomic(state / 'status.json', record)
    except Refusal as error:
        record.update(state='refused', reason_code=error.code, finished_at=now().isoformat())
    # Lock losers never replace the actual runner's status; all attempts remain individually inspectable.
    backup.write_private(state / (attempt + '.json'), json.dumps(record, sort_keys=True).encode() + b'\n')
    return record


def inspect(policy_path=POLICY, state=STATE):
    result = {'version': 1, 'eligible': False, 'provider_calls': 0}
    try:
        limits = policy(policy_path)
        result.update(eligible=True, policy_expires_at=limits['valid_until'],
                      scope_ceiling_bytes=limits['scope_storage_ceiling_bytes'],
                      daily_download_budget_bytes=limits['daily_download_budget_bytes'],
                      daily_request_budget=limits['daily_request_budget'])
    except Refusal as error:
        result['reason_code'] = error.code
    try:
        result['status'] = status_summary(read_json(Path(state) / 'status.json', {}))
    except Refusal:
        result.update(eligible=False, reason_code='state_invalid', status={'state': 'failed', 'reason_code': 'state_invalid'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'run'))
    parser.add_argument('--config', default=str(CONFIG))
    parser.add_argument('--policy', default=str(POLICY))
    parser.add_argument('--key-file', default=str(KEY))
    parser.add_argument('--backups', default=str(BACKUPS))
    parser.add_argument('--state-dir', default=str(STATE))
    args = parser.parse_args()
    if args.action == 'inspect':
        result = inspect(Path(args.policy), Path(args.state_dir))
        code = 0 if result['eligible'] else 2
    else:
        result = execute(state=Path(args.state_dir), policy_path=Path(args.policy), config_path=Path(args.config),
                         key=Path(args.key_file), backups=Path(args.backups))
        code = 0 if result['state'] == 'complete' else 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Automatic offsite backup refused. Inspect private attempt evidence; provider details withheld.')
