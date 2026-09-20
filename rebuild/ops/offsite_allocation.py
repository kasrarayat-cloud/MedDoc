"""Finite, evidence-bound allocation for the installed QuillMD B2 consumers.

The account bound is conditional on recorded administrative constraints. It is
not a claim that a restricted runtime credential can observe an entire account.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

try:
    from . import offsite_backup as offsite
except ImportError:
    import offsite_backup as offsite

ROOT = Path('/opt/meddoc-pro')
CONTRACT = offsite.CONFIG_PARENT / 'offsite-allocation.json'
EVIDENCE_ROOT = offsite.RUNTIME / 'offsite-account-evidence'
LEDGER = offsite.RUNTIME / 'automatic-offsite/budget.json'
HISTORY_DAY = '2026-09-20'
HISTORY_FLOOR = {'requests': 296, 'download_bytes': 68_551_020}
HELPER_PATH = offsite.RUNTIME / 'b2-offsite-20260920/inventory_approved_prefix.py'
HELPER_ORIGINAL_SHA256 = '348f579da63694dde887a7c955bccaca4643775d5c1b76866670faa9eb1b2a7d'
RETIRED_HELPER_STUB = (b'#!/usr/bin/env python3\n'
                      b'raise SystemExit("Historical unbudgeted inventory is retired. Use the reviewed '
                      b'rebuild/ops/offsite_operator.py inventory command with shared accounting.")\n')
SOURCES = tuple('rebuild/ops/' + name + '.py' for name in
                ('automatic_offsite', 'offsite_backup', 'offsite_operator', 'offsite_allocation', 'install_offsite_policy'))
CONSUMERS = ['scheduled_upload', 'manual_upload', 'verification_readback',
             'isolated_restore', 'metadata_inspection', 'operator_external_reservation']
CONSTRAINTS = [
    'all_known_quillmd_consumers_use_canonical_lock_policy_and_ledger',
    'no_unregistered_prefix_writer_during_validity',
    'reserve_external_requests_before_activity_or_suspend_schedule',
    'invalidate_before_other_account_storage_cap_or_credential_changes',
    'account_inventory_renewal_requires_owner_desktop_access',
    'unknown_account_credentials_are_not_claimed_absent',
]


def require(value):
    if not value:
        raise ValueError('Allocation evidence or installed controls are invalid.')


def stamp(value):
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None)
    return result.astimezone(timezone.utc)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def artifact(spec, directory):
    require(type(spec) is dict and set(spec) == {'name', 'local_sha256'})
    require(spec['name'] in ('account-audit.json', 'operating-evidence.json', 'provenance.json'))
    raw = offsite.read_private(directory / spec['name'], 262144)
    require(digest(raw) == spec['local_sha256'])
    return json.loads(raw)


def validate(limits, policy_path, at, *, contract_path=None):
    """No network, no state writes. Rechecked before every live HTTP attempt."""
    if contract_path is None:
        marker = offsite.CONFIG_PARENT / 'offsite-policy-installing.json'
        require(not marker.exists() and not marker.is_symlink())
    if HELPER_PATH.exists() or HELPER_PATH.is_symlink():
        require(offsite.read_private(HELPER_PATH, 262144) == RETIRED_HELPER_STUB)
    raw = offsite.read_private(contract_path or CONTRACT, 262144)
    item = json.loads(raw)
    fields = {'version', 'status', 'policy_sha256', 'observed_at', 'valid_until',
              'evidence_directory', 'audit', 'operating_evidence', 'provenance',
              'windows_source_sha256', 'control_sources', 'known_consumers',
              'administrative_constraints', 'non_scope_observed_bytes',
              'account_reserved_bound_bytes', 'renewal_requires_desktop',
              'key_inventory_complete', 'future_budget_guarantee'}
    require(type(item) is dict and set(item) == fields and item['version'] == 1
            and item['status'] == 'active')
    ledger = json.loads(offsite.read_private(LEDGER, 4 * 1024 * 1024))
    require(type(ledger) is dict and ledger.get('version') in (1, 2))
    history = ledger if ledger['version'] == 1 and ledger.get('day') == HISTORY_DAY else ledger.get('days', {}).get(HISTORY_DAY, {})
    require(all(type(history.get(key)) is int and history[key] >= floor for key, floor in HISTORY_FLOOR.items()))
    policy_bytes = offsite.read_private(Path(policy_path), 16384)
    require(item['policy_sha256'] == digest(policy_bytes) and json.loads(policy_bytes) == limits)
    start, end = stamp(item['observed_at']), stamp(item['valid_until'])
    require(start == stamp(limits['observed_at']) and end == stamp(limits['valid_until'])
            and start <= at < end and end - start <= timedelta(hours=24))
    require(item['known_consumers'] == CONSUMERS and item['administrative_constraints'] == CONSTRAINTS)
    require(item['renewal_requires_desktop'] is True and item['key_inventory_complete'] is False
            and item['future_budget_guarantee'] is False)
    require(type(item['control_sources']) is dict and set(item['control_sources']) == set(SOURCES))
    for relative, expected in item['control_sources'].items():
        path = ROOT / relative
        require(path.resolve() == path and digest(path.read_bytes()) == expected)
    directory = Path(item['evidence_directory'])
    require(directory.parent == EVIDENCE_ROOT and directory.resolve() == directory)
    audit = artifact(item['audit'], directory)
    updated = artifact(item['operating_evidence'], directory)
    provenance = artifact(item['provenance'], directory)
    require(item['audit']['name'] == 'account-audit.json'
            and item['operating_evidence']['name'] == 'operating-evidence.json'
            and item['provenance']['name'] == 'provenance.json')
    require(audit['status'] == 'verified_over_observed_interval'
            and audit['stable_over_two_scans'] is True and audit['complete_account_total'] is True
            and audit['future_budget_guarantee'] is False and len(audit['scans']) == 2)
    first, last = audit['scans']
    require(first['buckets'] == last['buckets'] and stamp(first['completed_at']) <= stamp(last['started_at'])
            and stamp(first['started_at']) < stamp(first['completed_at'])
            and stamp(last['started_at']) < stamp(last['completed_at']) == start)
    total = scope = 0
    require(len({bucket['bucket_id'] for bucket in last['buckets']}) == len(last['buckets']))
    for bucket in last['buckets']:
        for key in ('retained_upload_versions', 'retained_version_bytes', 'quillmd_scope_bytes',
                    'version_start_markers', 'unfinished_uploads'):
            require(type(bucket[key]) is int and bucket[key] >= 0)
        require(bucket['version_start_markers'] == bucket['unfinished_uploads'] == 0)
        require(bucket['quillmd_scope_bytes'] <= bucket['retained_version_bytes'])
        if bucket['is_quillmd_bucket']:
            require(bucket['bucket_id'] == limits['bucket_id'] and bucket['bucket_type'] == 'allPrivate')
        else:
            require(bucket['quillmd_scope_bytes'] == 0)
        total += bucket['retained_version_bytes']
        scope += bucket['quillmd_scope_bytes']
    require(sum(bucket['is_quillmd_bucket'] is True for bucket in last['buckets']) == 1)
    for scan in audit['scans']:
        require(scan['complete_account_total'] is True and scan['unfinished_part_bytes'] == 0
                and scan['completed_version_bytes'] == scan['account_total_bytes'] == total
                and scan['quillmd_scope_bytes'] == scope)
    require(total == audit['account_total_bytes'] == limits['account_storage_used_bytes_at_observation']
            and scope == audit['quillmd_scope_bytes'] == limits['scope_storage_bytes_at_observation'])
    observation = updated['account_audit']
    require(observation['source_sha256'] == item['windows_source_sha256']
            and observation['fully_paginated'] is True and observation['matching_scans'] == 2
            and observation['key_inventory_complete'] is False and observation['future_budget_guarantee'] is False
            and stamp(observation['observed_end']) == start
            and observation['account_storage_bytes'] == total and observation['scope_storage_bytes'] == scope
            and observation['unfinished_uploads'] == observation['unfinished_part_bytes'] == 0)
    require(observation['buckets'] == len(last['buckets'])
            and observation['retained_versions'] == sum(b['retained_upload_versions'] for b in last['buckets'])
            and stamp(observation['observed_start']) == stamp(first['started_at']))
    scope_inventory = next(bucket['inventory_sha256'] for bucket in last['buckets'] if bucket['is_quillmd_bucket'])
    require(isinstance(scope_inventory, str) and re.fullmatch('[a-f0-9]{64}', scope_inventory)
            and observation['inventory_sha256'] == scope_inventory
            and re.fullmatch('[a-f0-9]{64}', item['windows_source_sha256']))
    require(updated['audit_cleanup']['fresh_authorization_http_status'] == 401
            and updated['audit_cleanup']['runtime_fresh_authorization_http_status'] == 200
            and updated['audit_cleanup']['runtime_exact_scope_verified'] is True)
    caps = updated['provider_caps_observation']
    require(caps['storage_cap_display'] == '10 GB' and caps['storage_spend_cap_display'] == '$0.00'
            and caps['download_cap_display'] == '1 GB' and caps['download_spend_cap_display'] == '$0.00')
    require(type(caps['class_b_daily_cap']) is int and type(caps['class_c_daily_cap']) is int
            and limits['daily_request_budget'] <= min(caps['class_b_daily_cap'], caps['class_c_daily_cap']))
    # The bytes are an allocation bound, not a relabelled rounded daily counter.
    non_scope = total - scope
    bound = non_scope + limits['scope_storage_ceiling_bytes']
    require(type(item['non_scope_observed_bytes']) is int and item['non_scope_observed_bytes'] == non_scope
            and type(item['account_reserved_bound_bytes']) is int and item['account_reserved_bound_bytes'] == bound
            and bound <= limits['account_storage_limit_bytes'])
    require(limits['scope_storage_ceiling_bytes'] <= 1_000_000_000
            and limits['daily_download_budget_bytes'] <= 100_000_000
            and limits['daily_request_budget'] <= 500 and limits['max_run_seconds'] <= 900
            and limits['max_local_age_hours'] <= 30)
    require(provenance['vps_performed_account_scans'] is False
            and provenance['original_windows_byte_hash_independently_verified'] is False
            and provenance['original_windows_bytes_available'] is False
            and provenance['semantic_consistency_verified'] is True
            and provenance['original_windows_artifact_sha256_reported'] == item['windows_source_sha256']
            and provenance['local_artifact_hashes'] == {
                item['audit']['name']: item['audit']['local_sha256'],
                item['operating_evidence']['name']: item['operating_evidence']['local_sha256']})
    return {'account_reserved_bound_bytes': bound, 'non_scope_observed_bytes': non_scope,
            'observed_at': item['observed_at'], 'valid_until': item['valid_until'],
            'renewal_requires_desktop': True, 'assumptions': list(CONSTRAINTS)}
