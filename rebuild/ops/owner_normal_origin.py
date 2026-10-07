"""One inert-by-default owner normal-origin transition after private acceptance.

The original encrypted population remains authoritative. The complete retained
synthetic campaign is independently re-read before the source transition, then
its exact current population is held unchanged. No login or provider call runs.
"""
import argparse
import ast
import base64
import copy
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import types
import uuid
from dotenv import dotenv_values
from . import legacy_model_activation as old
from . import repair_source_permissions as source_files

SOURCE = Path(__file__).resolve().parents[2]
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PYTHON = APP / '.venv/bin/python'
RUNTIME = APP / '.runtime'
EVIDENCE = RUNTIME / 'owner-demo-20261006'
BASE = '9fad5a65e196428726540da0f0936f70cc768d05'
SELF = 'rebuild/ops/owner_normal_origin.py'
TEST = 'rebuild/ops/test_owner_normal_origin.py'
ENTRY = 'scripts/prepare-owner-normal-origin.py'
DECL = 'docs/foundation/mutations/20261007-quillmd-owner-normal443.md'
TEMPLATE = 'rebuild/deploy/owner-normal-https.conf'
INGRESS = '/etc/nginx/sites-available/quillmd'
PRIVATE_INGRESS = '/etc/nginx/sites-available/quillmd-email-preview'
OLD_INGRESS_SHA = 'ff7320480fe823cbc1564e3c104ee41bac1dd5e1336f8772274af36a541a7a0a'
PRIVATE_INGRESS_SHA = 'cbc81159b1505fd566625062517bb18dd8d4706cd30b0e334e7fdceec659f21a'
CADDY_SHA = 'bf0c14729a4ae86ecf2e8ff34d9b5e68aeba55a0bb0c06879580bc73e3a23c87'
OUTPUT = EVIDENCE / 'owner-normal443-publication-v1'
ATTEMPT = EVIDENCE / 'owner-normal443-attempt-v1.json'
VERIFY_OUTPUT = EVIDENCE / 'owner-normal443-served-verification-v1'
VERIFY_ATTEMPT = EVIDENCE / 'owner-normal443-served-verification-attempt-v1.json'
ACCEPTANCE = 'rebuild/ops/owner_acceptance_v3.py'
RECOVERY_DECL = 'docs/foundation/mutations/20261007-quillmd-private-availability-recovery.md'
PRIVATE_OPS = frozenset((ACCEPTANCE, 'rebuild/ops/test_owner_acceptance_v3.py', 'scripts/run-owner-acceptance-v3.py', 'docs/foundation/mutations/20261007-quillmd-owner-acceptance-v3.md'))
FROZEN_V3 = '34d4d3bf0b9641a2f642717b33833beb7a7f49a0c043bc095e592c41a78b0023'
NATIVE = tuple('rebuild/ops/' + name + '.py' for name in (
    'managed_helper', 'private_storage', 'backup_restore', 'email_activation',
    'activation_exclusion', 'legacy_model_activation', 'repair_source_permissions',
    'publisher_verification', 'private_availability_recovery'))
ALLOWED = frozenset((DECL, TEMPLATE, 'rebuild/quillmd/settings.py', 'rebuild/core/preview_access.py',
    'rebuild/core/tests/test_owner_normal_origin.py', SELF, TEST, ENTRY))
SHARED_NAMES = b'    server_name quillmd.com www.quillmd.com app.quillmd.com admin.quillmd.com;'
RESTRICTED_NAMES = b'    server_name quillmd.com www.quillmd.com admin.quillmd.com;'
ACTIVE_PROTOCOL_QUALIFIED = True
PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED = True
INGRESS_PUBLICATION_QUALIFIED = True
SERVED_VERIFICATION_PROTOCOL_QUALIFIED = True
SERVED_VERIFICATION_POLICY = {
    'mode':'--verify-served','output':str(VERIFY_OUTPUT),'attempt':str(VERIFY_ATTEMPT),
    'requests':[{'actor':'doctor','method':'GET','path':'/'},
                {'actor':'admin','method':'GET','path':'/console/services/'}],
    'GET_requests_maximum':2,'existing_session_rows_updated_maximum':4,'new_session_rows':0,
    'audit_rows_added':1,'audit_action':'admin.services_read','audit_primary_key':'canonical UUID; no sequence',
    'clinical_writes':0,'authentication_submissions':0,'provider_calls':0,'automatic_retries':False,
    'SQL_statement_count':'not_instrumented','per_actor_request_interval_maximum_seconds':60,
    'pre_GET_session_reserve_seconds':600,'post_proof_session_reserve_seconds':60,
    'forward_interval_maximum_seconds':540,'completion_valid_only_without_STOP':True,
    'original_capture_and_campaign_intervals_immutable':True,
}
OUTER_SECONDS = 2400
RUNTIME_BINDING = 'private-acceptance-completion-cross-hashes-v1'
SESSION_FORWARD_RESERVE = 600
SESSION_COMPLETION_RESERVE = 60
PRIVATE_PATHS = {
    'private_acceptance': EVIDENCE / 'installed-acceptance-v3-20261007/complete.json',
    'private_report': EVIDENCE / 'installed-acceptance-v3-20261007/independent-verification.json',
    'private_authority': EVIDENCE / 'installed-acceptance-v3-preparation-20261007/parent-phase-verify.json',
    'availability': RUNTIME / 'private-availability-recovery-20261007/complete.json'}
PRIVATE_PHASE = EVIDENCE / 'installed-acceptance-v3-preparation-20261007/co-tenant-phase-preservation.json'
PRIVATE_PHASE_PROTOCOL = 'quill-only-phase-preservation-v1'

class Refusal(RuntimeError):
    pass

def require(condition, label):
    if not condition: raise Refusal(label)

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(value): return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
def qualified(): return ACTIVE_PROTOCOL_QUALIFIED and PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED and INGRESS_PUBLICATION_QUALIFIED

def application_gate(preview, settings):
    tree = ast.parse(preview)
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED'
                for target in node.targets)]
    require(len(values) == 1 and isinstance(values[0], ast.Constant) and values[0].value is True,
            'normal443_checked_application_qualified')
    setting = [node.value for node in ast.parse(settings).body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'
                for target in node.targets)]
    expected = ast.parse("os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', '0') == '1'", mode='eval').body
    require(len(setting) == 1 and ast.dump(setting[0], include_attributes=False)
        == ast.dump(expected, include_attributes=False), 'normal443_default_disabled_explicit_setting')
    return True

def render_ingress(original, template):
    require(type(original) is bytes and sha(original) == OLD_INGRESS_SHA, 'normal443_original_ingress_drift')
    require(original.count(SHARED_NAMES) == 1 and not original.count(RESTRICTED_NAMES), 'normal443_original_shared_names')
    require(type(template) is bytes and 0 < len(template) <= 16384 and b'\0' not in template, 'normal443_template_bytes')
    result = original.replace(SHARED_NAMES, RESTRICTED_NAMES, 1) + b'\n' + template
    require(len(result) <= 128 * 1024, 'normal443_candidate_ingress_bound')
    require(result[:-len(template)-1].replace(RESTRICTED_NAMES, SHARED_NAMES, 1) == original,
            'normal443_other_ingress_bytes_preserved')
    return result

def contract(raw):
    matches = re.findall(rb'<!-- owner-normal443-contract -->\s*```json\s*(.*?)```', raw, re.S)
    require(len(matches) == 1, 'normal443_single_contract')
    result = json.loads(matches[0])
    require(result.get('format') == 1 and result.get('source_base') == BASE
        and result.get('approved_source_paths') == sorted(ALLOWED)
        and result.get('ingress_path') == INGRESS and result.get('original_ingress_sha256') == OLD_INGRESS_SHA
        and result.get('private_ingress_sha256') == PRIVATE_INGRESS_SHA and result.get('caddy_sha256') == CADDY_SHA
        and result.get('origin') == 'https://app.quillmd.com'
        and result.get('private_origin') == 'https://app.quillmd.com:9443'
        and result.get('provider_calls') == result.get('authentication_submissions') == result.get('database_writes') == 0
        and result.get('automatic_retries') is False and result.get('outer_ceiling_seconds') == OUTER_SECONDS,
        'normal443_exact_prospective_scope')
    require(result.get('runtime_receipt_binding_protocol') == RUNTIME_BINDING
        and result.get('private_phase_preservation') == {'path': str(PRIVATE_PHASE), 'binding': RUNTIME_BINDING}
        and result.get('private_acceptance_completed') is False
        and result.get('session_forward_reserve_seconds') == SESSION_FORWARD_RESERVE
        and result.get('session_completion_reserve_seconds') == SESSION_COMPLETION_RESERVE,
        'normal443_prospective_runtime_admission_contract')
    require(result.get('served_verification_policy') == SERVED_VERIFICATION_POLICY
        and result.get('served_verification_protocol_qualified') is SERVED_VERIFICATION_PROTOCOL_QUALIFIED,
        'normal443_exact_separate_served_verification_policy')
    return result

def source_gate(target):
    require(qualified(), 'normal443_source_protocol_unqualified')
    require(re.fullmatch('[a-f0-9]{40}', target or '') and SOURCE.is_relative_to(ROOT / '.worktrees')
        and SOURCE.resolve() == SOURCE and os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000,
        'normal443_operations_identity')
    require(old.git(SOURCE, 'rev-parse', 'HEAD').strip().decode() == target
        and old.git(ROOT, 'rev-parse', 'origin/main').strip().decode() == target
        and not old.git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(),
        'normal443_exact_clean_merged_source')
    old.git(SOURCE, 'merge-base', '--is-ancestor', BASE, target)
    require(set(old.git(SOURCE, 'diff', '--name-only', BASE, target).decode().splitlines()) == ALLOWED,
            'normal443_exact_source_scope')
    buffers = {}
    dependencies = (*NATIVE, ACCEPTANCE, RECOVERY_DECL, 'docs/foundation/mutations/20261007-quillmd-owner-acceptance-v3.md',
                    'scripts/check-citation.sh', 'scripts/lib/runs-api.sh')
    with source_files.open_root(SOURCE) as fd:
        for relative in dict.fromkeys((*sorted(ALLOWED), *dependencies)):
            index = old.git(SOURCE, 'ls-files', '-s', '--', relative).decode().split()
            require(len(index) >= 4 and index[0] in ('100644', '100755'), 'normal443_source_index_type')
            raw = source_files.operator_bytes(relative, 0o644 if index[0] == '100644' else 0o755, fd)
            require(raw == old.git(SOURCE, 'show', target + ':' + relative), 'normal443_source_bytes')
            if relative not in ALLOWED:
                require(raw == old.git(SOURCE, 'show', BASE + ':' + relative), 'normal443_unchanged_operational_dependency')
            buffers[relative] = raw
    result = contract(buffers[DECL])
    application_gate(buffers['rebuild/core/preview_access.py'], buffers['rebuild/quillmd/settings.py'])
    require(set(old.git(SOURCE, 'diff', '--name-only', result['private_accepted_revision'], BASE).decode().splitlines()) == PRIVATE_OPS, 'normal443_intermediate_four_operational_paths')
    require(all(result.get(key) is True for key in ('active_protocol_qualified', 'private_acceptance_protocol_qualified',
                'ingress_publication_qualified')), 'normal443_committed_qualification')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(os.environ.get('RULED_MUTATION_DECLARATION') == DECL and re.fullmatch('[a-f0-9]{40}', commit)
        and old.git(SOURCE, 'log', '-1', '--format=%H', '--', DECL).strip().decode() == commit
        and old.git(SOURCE, 'show', commit + ':' + DECL) == buffers[DECL], 'normal443_normal_ruled_door')
    require(os.environ.get('RULED_ACT_MAX_SECS') == str(OUTER_SECONDS), 'normal443_explicit_outer_ceiling')
    for revision in dict.fromkeys((BASE, target, result.get('private_accepted_revision'))):
        require(re.fullmatch('[a-f0-9]{40}', revision or ''), 'normal443_prior_revision_pin')
        source_files.sealed_citation(buffers['scripts/check-citation.sh'], buffers['scripts/lib/runs-api.sh'], revision)
    return result, buffers

def pinned_receipt(item, label, expected_path):
    require(isinstance(item, dict) and set(item) == {'path', 'sha256'}
        and item['path'] == str(expected_path) and re.fullmatch('[a-f0-9]{64}', item['sha256'] or ''), label)
    raw = source_files.protected(expected_path)
    require(sha(raw) == item['sha256'], label)
    return json.loads(raw), raw

def runtime_receipt(item, label, expected_path):
    require(isinstance(item, dict) and set(item) == {'path', 'binding'}
        and item['path'] == str(expected_path) and item['binding'] == RUNTIME_BINDING, label)
    raw = source_files.protected(expected_path)
    return json.loads(raw), raw

def private_receipts(policy):
    require(not any(os.path.lexists(path) for path in (
        PRIVATE_PATHS['private_acceptance'].parent / 'STOP.json',
        PRIVATE_PATHS['private_authority'].parent / 'STOP.json')),
        'normal443_private_campaign_stop_record_absent')
    values = {key: (pinned_receipt if key == 'availability' else runtime_receipt)(
                policy.get(key), 'normal443_' + key + '_pin', path) for key, path in PRIVATE_PATHS.items()}
    accepted, report, authority, availability = [values[key][0] for key in PRIVATE_PATHS]
    require(accepted.get('format') == 3 and accepted.get('complete') is True
        and accepted['operations_revision'] == BASE and accepted['served_revision'] == policy['private_accepted_revision']
        and accepted['independent_report'] == str(PRIVATE_PATHS['private_report'])
        and accepted['independent_report_sha256'] == sha(values['private_report'][1])
        and accepted['availability_preserved'] is True and accepted['provider_retries'] == 0,
        'normal443_completed_private_acceptance')
    require(report.get('complete') is True and report['operations_revision'] == BASE
        and report['served_revision'] == accepted['served_revision']
        and report['activation_sha256'] == policy['availability']['sha256']
        and report['provider_calls'] == report['database_writes'] == 0
        and {row['name'] for row in report['cases']} == {'soap-typed', 'custom-word-typed', 'soap-voice', 'allergy-missing', 'allergy-legitimate'}
        and len(report['cases']) == 5 and report['preservation']['all_36_tables_all_old_rows_columns_compared'] is True
        and report['preservation']['all_67_old_referenced_files_preserved'] is True,
        'normal443_complete_independent_private_report')
    require(authority['phase'] == 'verify' and authority['operations_revision'] == BASE
        and authority['served_revision'] == accepted['served_revision']
        and availability.get('complete') is True and availability['source']['operator_commit'] == accepted['served_revision'],
        'normal443_private_chain_identity')
    progress_path = PRIVATE_PATHS['private_acceptance'].parent / 'progress.json'
    progress_raw = source_files.protected(progress_path)
    progress = json.loads(progress_raw)
    require(report['browser_progress_sha256'] == sha(progress_raw)
        and progress['operations_revision'] == BASE and progress['served_revision'] == accepted['served_revision']
        and progress['activation_sha256'] == policy['availability']['sha256']
        and progress['browser_workflows_complete'] is True and progress['complete'] is False
        and progress['independent_readback_pending'] is True and not progress.get('failure')
        and {key:value for key,value in report['admin_readback'].items() if key != 'final_storage_state_verification'}
            == progress['admin_readback']
        and set(report['admin_readback']) == set(progress['admin_readback']) | {'final_storage_state_verification'}
        and {key:value for key,value in report['doctor_final_storage_state'].items() if key != 'verification'}
            == progress['doctor_final_storage_state']
        and set(report['doctor_final_storage_state']) == set(progress['doctor_final_storage_state']) | {'verification'},
        'normal443_completed_browser_cross_binding')
    require(authority['authority']['operations_revision'] == BASE
        and authority['authority']['served_revision'] == accepted['served_revision']
        and authority['authority']['availability_receipt_sha256'] == policy['availability']['sha256'],
        'normal443_final_authority_cross_binding')
    phase_raw = source_files.protected(PRIVATE_PHASE)
    observation = json.loads(phase_raw)
    require(type(observation) is dict, 'normal443_retained_private_phase_object')
    phase_pin = authority['authority'].get('phase_preservation', {})
    binding = observation.get('binding', {})
    proof = report.get('co_tenant_preservation_admission', {})
    require(type(phase_pin) is dict and set(phase_pin) == {'path', 'sha256', 'binding'}
        and phase_pin['path'] == str(PRIVATE_PHASE)
        and phase_pin['sha256'] == sha(phase_raw) == accepted.get('phase_preservation_sha256')
            == authority.get('phase_preservation_sha256')
        and phase_pin['binding'] == binding
        and type(binding) is dict and set(binding) == {'operations_revision', 'served_revision',
            'availability_receipt_sha256', 'parent_pid', 'parent_start_ticks', 'preparation_directory'}
        and binding['operations_revision'] == BASE and binding['served_revision'] == accepted['served_revision']
        and binding['availability_receipt_sha256'] == policy['availability']['sha256']
        and binding['preparation_directory'] == str(PRIVATE_PHASE.parent)
        and all(type(binding[name]) is int and binding[name] > 0
            and binding[name] == authority.get(name) for name in ('parent_pid', 'parent_start_ticks')),
        'normal443_retained_private_phase_file_binding')
    require(type(proof) is dict and proof.get('protocol') == observation.get('protocol') == PRIVATE_PHASE_PROTOCOL
        and proof.get('phase_observation_path') == str(PRIVATE_PHASE)
        and proof.get('phase_observation_sha256') == sha(phase_raw)
        and proof.get('phase_observation') == observation
        and accepted.get('co_tenant_preservation_admission') == proof,
        'normal443_retained_private_phase_proof_binding')
    for phase in ('before-auth', 'after-auth'):
        path = Path(authority['authority']['admissions'][phase]['path'])
        require(path == EVIDENCE / 'installed-acceptance-v3-preparation-20261007' / ('admission-' + phase + '.json'),
                'normal443_fixed_private_admission')
        packet, packet_raw = pinned_receipt(authority['authority']['admissions'][phase],
                                             'normal443_final_admission_hash', path)
        require(authority['admission_sha256'][phase] == sha(packet_raw)
            and progress['preparation'][phase] == packet and packet['operations_revision'] == BASE
            and packet['served_revision'] == accepted['served_revision'], 'normal443_private_admission_causal_chain')
        require(packet.get('co_tenant_preservation_admission') == proof,
                'normal443_retained_private_phase_admission_binding')
    values['progress'] = progress, progress_raw
    # The old native parent identity is retained history, never a live normal
    # controller. Current operation liveness is proved by check_hold separately.
    values['phase_preservation'] = observation, phase_raw
    return values

def normal_completion(policy, target):
    require(not os.path.lexists(OUTPUT / 'failed.json'), 'normal443_no_failed_normal_transition')
    raw = source_files.protected(OUTPUT / 'complete.json')
    value = json.loads(raw)
    require(value.get('format') == 1 and value.get('complete') is True and value.get('stage') == 'complete'
        and value.get('served_revision') == target and value.get('previous_served_revision') == policy['private_accepted_revision']
        and value.get('completion_valid_only_without_failed_receipt') is True
        and value.get('owner_normal_origin_enabled') is True and value.get('session_renewal_performed') is False
        and value.get('provider_calls') == value.get('authentication_submissions') == value.get('database_writes') == 0
        and value.get('full_original_and_new_acceptance_population_preserved') is True,
        'normal443_genuine_completed_normal_transition')
    attempt = json.loads(source_files.protected(ATTEMPT))
    require(attempt.get('attempt') == 1 and attempt.get('served_revision') == target and attempt.get('output') == str(OUTPUT)
        and attempt.get('automatic_retries') is False, 'normal443_original_single_transition_attempt')
    inputs = private_receipts(policy)
    require(value.get('private_acceptance_sha256') == sha(inputs['private_acceptance'][1]),
            'normal443_same_completed_private_campaign')
    return value, raw

SERVED_TABLES = frozenset('auth_group auth_group_permissions auth_permission core_auditevent core_code\ncore_codeset core_codesuggestion core_costreconciliation core_department core_encounter\ncore_invitation core_job core_ledgerentry core_loginattempt core_membership core_organization\ncore_patient core_payment core_platformcost core_providerreceipt core_refund core_reservation\ncore_servicehealth core_template core_templateversion core_usage core_user core_user_groups\ncore_user_user_permissions core_verification core_wallet core_webhookevent django_content_type\ndjango_migrations django_session otp_totp_totpdevice'.split())
SERVED_AUDIT_COLUMNS = frozenset(('id', 'created_at', 'actor_id', 'organization_id', 'department_id', 'action', 'target', 'details'))

class ServedDeltaRefusal(ValueError):
    pass

def served_require(value, message):
    if not value:
        raise ServedDeltaRefusal(message)

def served_uuid(value):
    served_require(isinstance(value, str), 'UUID string required')
    try:
        result = str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ServedDeltaRefusal('Canonical UUID required') from exc
    served_require(result == value, 'Canonical UUID required')
    return value

def served_payload_same(before, after):
    try:
        encoded = [json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) for value in (before, after)]
    except (TypeError, ValueError) as exc:
        raise ServedDeltaRefusal('Finite JSON session payload required') from exc
    return encoded[0] == encoded[1]

def served_copy_tables(tables):
    """Index every original raw row without decoding/normalizing COPY bytes."""
    served_require(isinstance(tables, dict) and set(tables) == SERVED_TABLES, 'Exact 36-table COPY population required')
    indexed = {}
    for table, packet in tables.items():
        served_require(isinstance(packet, dict) and set(packet) == {'columns', 'rows', 'primary_keys'}, 'Exact COPY table packet required')
        columns, rows, keys = (packet[name] for name in ('columns', 'rows', 'primary_keys'))
        served_require(isinstance(columns, list) and columns and all((isinstance(c, str) and c for c in columns)) and (len(set(columns)) == len(columns)) and isinstance(keys, list) and keys and (len(set(keys)) == len(keys)) and all((k in columns for k in keys)) and isinstance(rows, list), 'COPY schema and primary keys required')
        positions = [columns.index(key) for key in keys]
        result = {}
        for raw in rows:
            served_require(isinstance(raw, bytes) and raw.endswith(b'\n') and (b'\n' not in raw[:-1]) and (b'\r' not in raw), 'One complete byte COPY row required')
            cells = raw[:-1].split(b'\t')
            served_require(len(cells) == len(columns), 'COPY column count differs')
            key = tuple((cells[index] for index in positions))
            served_require(all((cell != b'\\N' for cell in key)) and key not in result, 'Null/duplicate COPY primary key')
            result[key] = (raw, dict(zip(columns, cells)))
        indexed[table] = result
    return indexed

def admit_served_deltas(before, after, keys, actors, intervals, secret, fingerprint, verifier):
    """Admit exact GET/save deltas using genuine frozen cryptographic helpers."""
    served_require(set(keys) == set(actors) == set(intervals) == {'doctor', 'admin'}, 'Exact doctor/admin inputs required')
    served_require(all((callable(getattr(verifier, name, None)) for name in ('normal_session', 'validate_admin_renewal', 'validate_preview_renewal', 'copy_value', 'parsed_timestamp'))), 'Checked frozen renewal verifier interface required')
    for actor in ('doctor', 'admin'):
        served_uuid(actors[actor])
        served_require(isinstance(keys[actor], dict) and set(keys[actor]) == {'normal', 'preview'}, 'Exact two named keys per actor')
        interval = intervals[actor]
        served_require(isinstance(interval, (list, tuple)) and len(interval) == 2 and all((isinstance(t, datetime) and t.tzinfo is not None and (t.utcoffset() is not None) for t in interval)) and (0 <= (interval[1] - interval[0]).total_seconds() <= 60), 'Measured aware bounded GET interval required')
    served_require(actors['doctor'] != actors['admin'], 'Distinct doctor/admin identities required')
    named = [keys[actor][kind] for actor in ('doctor', 'admin') for kind in ('normal', 'preview')]
    served_require(all((isinstance(key, str) and re.fullmatch('[a-z0-9]{32}', key) for key in named)) and len(set(named)) == 4, 'Four distinct existing session keys required')
    old, new = (served_copy_tables(before), served_copy_tables(after))
    for table in SERVED_TABLES:
        served_require(before[table]['columns'] == after[table]['columns'] and before[table]['primary_keys'] == after[table]['primary_keys'], 'COPY schema/primary keys changed: ' + table)
        if table not in {'django_session', 'core_auditevent'}:
            served_require(old[table] == new[table], 'Unrelated table/row changed: ' + table)
    session = before['django_session']
    served_require(set(session['columns']) == {'session_key', 'session_data', 'expire_date'} and session['primary_keys'] == ['session_key'], 'Exact Django session COPY schema required')
    audit = before['core_auditevent']
    served_require(set(audit['columns']) == SERVED_AUDIT_COLUMNS and audit['primary_keys'] == ['id'], 'Exact UUID AuditEvent COPY schema required')
    old_sessions, new_sessions = (old['django_session'], new['django_session'])
    served_require(set(old_sessions) == set(new_sessions), 'New/deleted session key refused')
    allowed = {(key.encode(),) for key in named}
    served_require(allowed <= set(old_sessions), 'Named original session missing')
    for key, row in old_sessions.items():
        if key not in allowed:
            served_require(new_sessions[key] == row, 'Unrelated session changed')
    evidence = []
    for actor in ('doctor', 'admin'):
        for kind in ('normal', 'preview'):
            key = (keys[actor][kind].encode(),)
            old_raw, prior = old_sessions[key]
            new_raw, current = new_sessions[key]
            served_require(prior['session_key'] == current['session_key'] == key[0], 'Existing session identity changed')
            previous = verifier.normal_session(prior['session_data'], secret)
            following = verifier.normal_session(current['session_data'], secret)
            served_require(isinstance(previous, dict) and isinstance(following, dict), 'Authenticated session dictionary required')
            prior_expiry = verifier.parsed_timestamp(prior['expire_date'])
            served_require(prior_expiry.tzinfo is not None and prior_expiry.utcoffset() is not None and (prior_expiry > intervals[actor][0]), 'Original named database session expired at GET start')
            if kind == 'normal':
                served_require(served_payload_same(previous, following) and str(previous.get('_auth_user_id')) == actors[actor], 'Authenticated normal payload/actor changed')
                if actor == 'admin':
                    served_require(isinstance(previous.get('otp_device_id'), str) and re.fullmatch('otp_totp.totpdevice/[1-9][0-9]*', previous['otp_device_id']), 'Original admin MFA identity missing/invalid')
                renewal = verifier.validate_admin_renewal(current, following, intervals[actor])
            else:
                renewal = verifier.validate_preview_renewal(current, following, intervals[actor], fingerprint, previous)
                old_payload, new_payload = (copy.deepcopy(previous), copy.deepcopy(following))
                for payload in (old_payload, new_payload):
                    payload['grant'].pop('seen', None)
                    payload.pop('_session_expiry', None)
                served_require(served_payload_same(old_payload, new_payload), 'Preview payload JSON types/values changed')
            changes = [column for column in session['columns'] if prior[column] != current[column]]
            served_require(set(changes) <= {'session_data', 'expire_date'}, 'Unexpected session column changed')
            evidence.append({'actor': actor, 'kind': kind, 'actor_id': actors[actor], 'session_key_sha256': sha(key[0]), 'before_row_sha256': sha(old_raw), 'after_row_sha256': sha(new_raw), 'changed_columns': changes, 'renewal': renewal})
    old_audit, new_audit = (old['core_auditevent'], new['core_auditevent'])
    served_require(set(old_audit) <= set(new_audit), 'Original AuditEvent removed')
    for key, row in old_audit.items():
        served_require(new_audit[key] == row, 'Original AuditEvent bytes changed')
    added = set(new_audit) - set(old_audit)
    served_require(len(added) == 1, 'Exactly one genuine admin.services_read UUID AuditEvent required')
    audit_key = next(iter(added))
    audit_raw, row = new_audit[audit_key]
    audit_id = served_uuid(verifier.copy_value(row['id']).decode())
    served_require(row['id'] == audit_id.encode(), 'Canonical UUID COPY identity required')
    served_require(row['actor_id'] == actors['admin'].encode() and row['organization_id'] == row['department_id'] == b'\\N' and (row['action'] == b'admin.services_read') and (row['target'] == b''), 'Unexpected admin.services_read identity/fields')
    try:
        details = json.loads(verifier.copy_value(row['details']))
    except (ValueError, UnicodeError) as exc:
        raise ServedDeltaRefusal('AuditEvent JSON details invalid') from exc
    served_require(isinstance(details, dict) and details == {}, 'Unexpected admin.services_read details')
    created = verifier.parsed_timestamp(row['created_at'])
    served_require(created.tzinfo is not None and created.utcoffset() is not None and (intervals['admin'][0] <= created <= intervals['admin'][1]), 'AuditEvent outside actual admin GET interval')
    return {'projected_tables': copy.deepcopy(after), 'session_renewals': evidence, 'session_rows_changed': sum((bool(item['changed_columns']) for item in evidence)), 'audit_addition': {'id': audit_id, 'action': 'admin.services_read', 'actor_id': actors['admin'], 'created_at': created.isoformat(), 'row_sha256': sha(audit_raw)}, 'unchanged_tables': sorted(SERVED_TABLES - {'django_session', 'core_auditevent'}), 'new_session_keys': 0, 'database_writes_by_admission': 0, 'authentication_submissions': 0, 'provider_calls': 0}

def live_session_admission(states, rows, actors, secret, fingerprint, decoder, at, minimum, *, admin_device):
    """Observe existing live grants; do not renew or manufacture their freshness."""
    require(set(states) == set(actors) == {'doctor', 'admin'} and isinstance(rows, dict)
        and callable(decoder) and type(minimum) is int and minimum >= 0
        and isinstance(at, datetime) and at.tzinfo is not None
        and re.fullmatch('otp_totp.totpdevice/[1-9][0-9]*', admin_device or ''), 'normal443_live_session_inputs')
    now = at.timestamp(); expected = {}; limits = {}; evidence = {}
    for actor, state in states.items():
        require(isinstance(state, dict) and set(state) == {'cookies', 'origins'} and state['origins'] == []
            and isinstance(state['cookies'], list) and len(state['cookies']) == 3,
            'normal443_final_storage_state_shape')
        names = {'__Host-quillmd_preview': 'Lax', 'quillmd_doctor_session': 'Strict', 'quillmd_doctor_csrf': 'Strict'}
        cookies = {item.get('name'): item for item in state['cookies']}
        require(set(cookies) == set(names) and len(cookies) == len(state['cookies']), 'normal443_final_cookie_population')
        for name, site in names.items():
            item = cookies[name]
            require(item['domain'] == 'app.quillmd.com' and item['path'] == '/' and item['secure'] is True
                and item['httpOnly'] is True and item['sameSite'] == site and isinstance(item['value'], str)
                and item['value'], 'normal443_final_cookie_contract')
        doctor, preview = (cookies[name] for name in ('quillmd_doctor_session', '__Host-quillmd_preview'))
        for cookie in (doctor, preview):
            key = cookie['value']
            require(re.fullmatch('[a-z0-9]{32}', key) and key not in expected
                and type(cookie['expires']) in (int, float) and math.isfinite(cookie['expires']),
                'normal443_named_unique_existing_session')
            expected[key] = actor
            require(key in rows and set(rows[key]) == {'session_key', 'session_data', 'expire_date'}
                and rows[key]['session_key'] == key, 'normal443_existing_session_row')
            expiry = rows[key]['expire_date']
            expiry = datetime.fromisoformat(expiry) if isinstance(expiry, str) else expiry
            require(isinstance(expiry, datetime) and expiry.tzinfo is not None, 'normal443_aware_session_expiry')
            limits[actor + ':' + cookie['name'] + ':database'] = expiry.timestamp()
            limits[actor + ':' + cookie['name'] + ':browser'] = cookie['expires']
        normal = decoder(rows[doctor['value']]['session_data'].encode(), secret)
        grant = decoder(rows[preview['value']]['session_data'].encode(), secret)
        require(str(normal.get('_auth_user_id')) == actors[actor]
            and (actor != 'admin' or normal.get('otp_device_id') == admin_device),
            'normal443_existing_actor_and_mfa_payload')
        require(set(grant) == {'kind', 'grant', 'flows', '_session_expiry'} and grant['kind'] == 'quillmd-preview-v1'
            and isinstance(grant['flows'], dict) and set(grant['grant']) == {'fingerprint', 'issued', 'seen'}
            and grant['grant']['fingerprint'] == fingerprint, 'normal443_existing_preview_payload')
        issued, seen = (grant['grant'][name] for name in ('issued', 'seen'))
        require(all(type(value) in (int, float) and math.isfinite(value) for value in (issued, seen))
            and issued <= seen <= now and 0 <= now - issued < 7200 and 0 <= now - seen < 1800,
            'normal443_existing_grant_currently_valid')
        limits[actor + ':preview:idle'] = seen + 1800
        limits[actor + ':preview:absolute'] = issued + 7200
        evidence[actor] = {'actor_id': actors[actor], 'session_keys_sha256': [sha(item['value'].encode()) for item in (doctor, preview)],
            'rows_sha256': [sha(encode({**rows[item['value']], 'expire_date':
                rows[item['value']]['expire_date'].isoformat() if isinstance(rows[item['value']]['expire_date'], datetime)
                else rows[item['value']]['expire_date']})) for item in (doctor, preview)],
            'storage_state_sha256': sha(encode(state)), 'normal_MFA_payload_present': actor == 'admin',
            'preview_issued': issued, 'preview_seen': seen}
    require(set(rows) == set(expected) and len(rows) == 4, 'normal443_exact_four_existing_session_rows')
    remaining = min(limits.values()) - now
    require(remaining > minimum, 'normal443_existing_session_remaining_ttl')
    return {'observed_at': at.isoformat(), 'remaining_seconds': remaining, 'required_remaining_seconds': minimum,
        'expires_at_by_boundary': limits, 'actors': evidence, 'session_renewal_performed': False,
        'authentication_submissions': 0, 'provider_calls': 0, 'database_writes': 0}

def controlled_environment(original, previous, target, *, enabled):
    values = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == previous and values.get('QUILLMD_APP_BASE_URL') == 'https://app.quillmd.com:9443'
        and values.get('QUILLMD_PREVIEW_AUTH_ENABLED') == '1'
        and values.get('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED') in (None, '', '0', '1'), 'normal443_original_environment')
    require(re.fullmatch('[a-f0-9]{40}', target or '') and type(enabled) is bool, 'normal443_environment_target')
    assignments = {'QUILLMD_RELEASE_SHA': target, 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': '1' if enabled else '0'}
    result, counts = [], {key: 0 for key in assignments}
    for line in original.splitlines(keepends=True):
        match = old.ASSIGNMENT.match(line)
        key = match[1].decode() if match else None
        if key in assignments:
            counts[key] += 1; result.append((key + '="' + assignments[key] + '"\n').encode())
        else: result.append(line)
    require(counts['QUILLMD_RELEASE_SHA'] == 1 and counts['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'] <= 1,
            'normal443_duplicate_controlled_assignment')
    if counts['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'] == 0:
        require(not result or result[-1].endswith(b'\n'), 'normal443_environment_append_separator')
        result.append(('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="' + assignments['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'] + '"\n').encode())
    updated = b''.join(result)
    after = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    require(all(after.get(key) == value for key, value in assignments.items())
        and {key: value for key, value in values.items() if key not in assignments}
          == {key: value for key, value in after.items() if key not in assignments}, 'normal443_only_two_environment_values')
    return updated

def compare_guard(before, after, *, ingress=None):
    require(set(before) == set(after), 'normal443_guard_population')
    for key in ('database', 'files', 'mail', 'static'):
        require(before[key] == after[key], 'normal443_guard_' + key)
    expected = dict(before['configuration'])
    if ingress is not None: expected[INGRESS] = ingress
    require(expected == after['configuration'], 'normal443_only_declared_ingress_delta')
    require(after['database']['pending_jobs'] == after['database']['held'] == 0,
            'normal443_idle_worker_finances')
    return True

def memory_verifier(module, *, installed_inventory=None):
    """Remove only the checked exclusive output sink; return its complete report."""
    require(sha(module.__authenticated_source) == FROZEN_V3, 'normal443_frozen_verifier_hash')
    function = copy_function(module.__authenticated_source, 'verify')
    constants = [node for node in ast.walk(function) if isinstance(node, ast.Constant) and node.value == 'installed-acceptance-v2-20261006']
    require(len(constants) == 4 and {node.lineno for node in constants} == {942,973,998,1044}, 'normal443_exact_campaign_literals')
    for node in constants: node.value = Path(module.CAMPAIGN).name
    # The checked current acceptance adapter adds these two independent final
    # state proofs. Reconstruct the same additions from the frozen function;
    # otherwise removing its output sink would accidentally drop those checks.
    for name in ('validate_admin_final_storage', 'validate_doctor_final_storage'):
        require(callable(module.__dict__.get(name)), 'normal443_checked_final_state_helpers')
    assignments = [node for node in function.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'admin_end']
    expected = ast.parse("admin_end=datetime.fromisoformat(readback['finished_at'].replace('Z','+00:00'))").body[0]
    require(len(assignments) == 1 and ast.dump(assignments[0], include_attributes=False)
        == ast.dump(expected, include_attributes=False), 'normal443_exact_final_state_interval_adapter')
    position = function.body.index(assignments[0]) + 1
    function.body[position:position] = ast.parse(
        "readback['final_storage_state_verification']=validate_admin_final_storage(progress)\n"
        "progress['doctor_final_storage_state']['verification']=validate_doctor_final_storage(progress)").body
    reports = [node.value for node in function.body if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'report'
        and isinstance(node.value, ast.Dict)]
    require(len(reports) == 1, 'normal443_exact_complete_report')
    reports[0].keys.append(ast.Constant('doctor_final_storage_state'))
    reports[0].values.append(ast.parse("progress['doctor_final_storage_state']", mode='eval').body)
    require(len(function.body) > 5 and ast.unparse(function.body[-5]) == 'destination = Path(args.output)'
        and isinstance(function.body[-4], ast.Expr) and isinstance(function.body[-3], ast.Assign)
        and isinstance(function.body[-2], ast.With) and isinstance(function.body[-1], ast.Expr)
        and 'os.O_EXCL' in ast.unparse(function.body[-3])
        and ast.unparse(function.body[-1]).startswith('print(json.dumps('), 'normal443_exact_report_sink')
    function.body[-5:] = [ast.Return(value=ast.Name(id='report', ctx=ast.Load()))]
    if installed_inventory is not None:
        require(callable(installed_inventory), 'normal443_checked_normal_inventory_admission')
        comparisons = [node for node in ast.walk(function) if isinstance(node, ast.Compare)
            and ast.unparse(node) == 'sha((APP.parent / name).read_bytes()) == value']
        require(len(comparisons) == 1, 'normal443_exact_installed_inventory_comparison')
        original = comparisons[0]
        replacement = ast.Call(func=ast.Name(id='normal_installed_inventory_path',ctx=ast.Load()),
            args=[ast.Name(id='name',ctx=ast.Load()),ast.Name(id='value',ctx=ast.Load())],keywords=[])
        class Replace(ast.NodeTransformer):
            def visit_Compare(self, node):
                return ast.copy_location(replacement,node) if node is original else self.generic_visit(node)
        function = Replace().visit(function)
    namespace = dict(module.__dict__)
    if installed_inventory is not None: namespace['normal_installed_inventory_path'] = installed_inventory
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), module.__file__, 'exec'), namespace)
    return namespace['verify'], namespace

def copy_function(raw, name):
    import copy
    nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, 'normal443_exact_frozen_function')
    return copy.deepcopy(nodes[0])

def normal_service_verifier(module, raw, host, completion):
    require(sha(raw)==FROZEN_V3,'normal443_frozen_service_verifier_identity')
    function=copy_function(raw,'verify_service_identity')
    namespace=dict(module.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),module.__file__,'exec'),namespace)
    actual_services=namespace['verify_service_identity']
    def services(release,activation,storage):
        require(release==host.served,'normal443_unchanged_private_workflow_release')
        require(host.boundary(host.operations)==completion['units_after'],'normal443_same_actual_normal_services')
        result=actual_services(host.operations,{'units_after':completion['units_after']['units']},storage)
        require(host.boundary(host.operations)==completion['units_after'],'normal443_same_actual_normal_services')
        return {**result,'current_served_revision':host.operations,'private_workflow_served_revision':release,
            'completion_unit_provenance':completion['units_after']['completion_unit_provenance']}
    return services

def admitted_served_projection(module, projection):
    tables={'django_session','core_auditevent'}
    require(set(projection)=={'post_populations','projected_populations','columns','primary_keys'}
        and all(set(projection[key])==tables for key in projection), 'normal443_exact_two_table_projection')
    genuine_mapping=module.row_mapping
    def mapping(table,lines,columns,primary_keys):
        actual=genuine_mapping(table,lines,columns,primary_keys)
        if table in tables and actual==projection['post_populations'][table]:
            require(columns==projection['columns'][table] and primary_keys==projection['primary_keys'][table],
                    'normal443_projection_actual_column_identity')
            return copy.deepcopy(projection['projected_populations'][table])
        return actual
    return mapping

def normal_controller_command(operations, source, mode, pid, started, acquired, deadline, *,
                              parse_start,
                              monotonic=time.monotonic,
                              read_bytes=lambda path: Path(path).read_bytes(),
                              read_text=lambda path: Path(path).read_text()):
    """Authenticate this normal controller; never reinterpret private authority."""
    now = monotonic()
    require(pid == os.getpid() and os.getuid() == os.geteuid() == 1000
        and mode in ('--execute', '--preflight', '--verify-served') and re.fullmatch('[a-f0-9]{40}', operations or '')
        and type(acquired) in (int, float) and type(deadline) in (int, float)
        and math.isfinite(acquired) and math.isfinite(deadline)
        and 0 < acquired <= now < deadline and callable(parse_start), 'normal443_own_controller_interval')
    proc = Path('/proc') / str(pid)
    command = [str(PYTHON), '-B', str(source / ENTRY), mode, '--operations-revision', operations]
    raw = read_bytes(proc / 'cmdline')
    require(raw == b'\0'.join(value.encode() for value in command) + b'\0', 'normal443_own_fixed_command')
    # The existing authenticated process-start parser handles parentheses in
    # native comm names; no string split silently changes its field position.
    require(parse_start(read_text(proc / 'stat')) == started, 'normal443_own_process_reused')
    return {'controller': 'normal443', 'parent_pid': pid, 'parent_start_ticks': started,
            'own_mode': mode, 'argv_sha256': sha(raw), 'acquired_monotonic': acquired,
            'deadline_monotonic': deadline}

class NativeHost:
    source = SOURCE
    def __init__(self, policy, target, buffers, started, *, mode='--execute'):
        require(qualified(), 'normal443_source_protocol_unqualified')
        self.policy, self.operations, self.buffers = policy, target, buffers
        self.deadline = started + OUTER_SECONDS
        self.mode = mode; self.parent_pid = os.getpid()
        self.served = policy['private_accepted_revision']
        self.inside = False; self.lock_rows = []; self.alignment = None
        self.acceptance = types.ModuleType('_quillmd_normal443_acceptance_' + target)
        self.acceptance.__file__ = str(SOURCE / ACCEPTANCE)
        exec(compile(buffers[ACCEPTANCE], self.acceptance.__file__, 'exec'), self.acceptance.__dict__)
        self.acceptance.execution_gate()
        package = self.acceptance.checked_native_modules(self)
        self.old, self.recovery = package.legacy_model_activation, package.private_availability_recovery
        self.exclusion, self.backup, self.env_writer, self.managed, self.storage = self.old.modules()
        self.native = self.old.Host(self.managed)
        self.common, self.verifier, self.historical_policy = self.acceptance.frozen_modules()
        self.inputs = private_receipts(policy)
        self.authority = self.inputs['private_authority'][0]['authority']
        require(self.authority['operations_revision'] == BASE and self.authority['served_revision'] == self.served,
                'normal443_actual_private_authority')
        for phase in ('before-auth', 'after-auth'):
            item = self.authority['admissions'][phase]
            pinned_receipt(item, 'normal443_private_admission_hash', self.acceptance.PREPARATION / ('admission-' + phase + '.json'))
        self.original_environment = self.old.protected(APP / '.env', 65536)
        self.cipher = self.backup.key_at(self.old.KEY)
        values = dotenv_values(stream=StringIO(self.original_environment.decode()), interpolate=False)
        self.session_secret = values['QUILLMD_SECRET_KEY']
        from django.utils.crypto import salted_hmac
        self.preview_fingerprint = salted_hmac('quillmd-preview-v1', values['QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME']
            + '\0' + values['QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD'], secret=self.session_secret).hexdigest()
        del values
        self.forward_deadline = None

    def git(self, tree, *args): return old.git(tree, *args)
    def read_source(self, path):
        relative = str(Path(path).relative_to(SOURCE))
        require(relative in self.buffers, 'normal443_checked_module_read')
        return self.buffers[relative]
    def check(self, reserve=0):
        now = time.monotonic()
        require(now + reserve < self.deadline, 'normal443_outer_deadline')
        if getattr(self, 'forward_deadline', None) is not None and not getattr(self, 'rolling_back', False):
            require(now < self.forward_deadline, 'normal443_bounded_forward_interval')
    def forward_budget(self):
        self.check(500)
        self.forward_deadline = time.monotonic() + SESSION_FORWARD_RESERVE - SESSION_COMPLETION_RESERVE

    def check_private_inputs(self):
        current = private_receipts(self.policy)
        require(set(current) == set(self.inputs)
            and all(current[key][1] == value[1] for key, value in self.inputs.items()),
            'normal443_completed_private_inputs_unchanged')
        return current

    def session_admission(self, minimum):
        """Read current rows and the genuine final browser state; no HTTP request."""
        import psycopg
        from psycopg.rows import dict_row
        self.check_hold()
        self.check_private_inputs()
        progress = self.inputs['progress'][0]
        readback = progress['admin_readback']
        private_report = self.inputs['private_report'][0]
        admin_proof = self.acceptance.validate_admin_final_storage(progress)
        doctor_proof = self.acceptance.validate_doctor_final_storage(progress)
        require(admin_proof == private_report['admin_readback']['final_storage_state_verification']
            and doctor_proof == private_report['doctor_final_storage_state']['verification'],
            'normal443_same_genuine_final_storage_proofs')
        directory = PRIVATE_PATHS['private_acceptance'].parent
        doctor = progress['doctor_final_storage_state']
        admin = {'path': readback['final_storage_state_path'], 'sha256': readback['final_storage_state_sha256'],
                 'captured_at': readback['final_storage_state_captured_at']}
        states = {}
        for actor, item, path in (('doctor', doctor, directory / 'browser-session.json'),
                                  ('admin', admin, directory / 'admin-browser-session-after-readback.json')):
            require(set(item) == {'path', 'sha256', 'captured_at'}, 'normal443_final_storage_state_binding')
            state, raw = pinned_receipt({'path': item['path'], 'sha256': item['sha256']},
                                         'normal443_final_storage_state_hash', path)
            captured = datetime.fromisoformat(item['captured_at'].replace('Z', '+00:00'))
            begin = datetime.fromisoformat(progress['started'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(progress['finished'].replace('Z', '+00:00'))
            require(begin <= captured <= end and captured.tzinfo is not None,
                    'normal443_genuine_final_state_capture_interval')
            if actor == 'admin':
                require(datetime.fromisoformat(progress['clinical_workflows_completed_at'].replace('Z', '+00:00'))
                    <= datetime.fromisoformat(readback['started_at'].replace('Z', '+00:00')) <= captured
                    <= datetime.fromisoformat(readback['finished_at'].replace('Z', '+00:00')),
                    'normal443_admin_state_after_clinical_campaign')
            states[actor] = state
        actors = {str(row['quoted_user']) for row in progress['attempts']}
        require(len(actors) == 1, 'normal443_original_campaign_actor')
        actors = {'doctor': actors.pop(), 'admin': str(readback['actor_id'])}
        auth = json.loads(self.acceptance.protected(self.acceptance.ADMIN / 'normal-authentication.json'))
        meta_raw = self.acceptance.protected(self.acceptance.ADMIN / 'metadata-after-normal-mfa.json')
        require(sha(meta_raw) == auth['authentication_metadata']['normal_mfa_sha256']
            and str(auth['actor_id']) == actors['admin'], 'normal443_existing_admin_device_evidence')
        admin_device = 'otp_totp.totpdevice/' + str(json.loads(meta_raw)['device']['id'])
        keys = [cookie['value'] for state in states.values() for cookie in state['cookies']
                if cookie['name'] in ('quillmd_doctor_session', '__Host-quillmd_preview')]
        require(len(keys) == len(set(keys)) == 4, 'normal443_exact_named_final_session_keys')
        with psycopg.connect(**self.backup.source_options(APP, self.old.ROLES), row_factory=dict_row) as conn:
            self.acceptance.readonly_connection_flags(conn)
            rows = conn.execute('SELECT session_key,session_data,expire_date FROM django_session WHERE session_key=ANY(%s)',
                                (keys,)).fetchall()
            require(len(rows) == 4, 'normal443_four_existing_live_session_rows')
            result = live_session_admission(states, {row['session_key']: dict(row) for row in rows}, actors,
                self.session_secret, self.preview_fingerprint, self.verifier.normal_session,
                datetime.now(timezone.utc), minimum, admin_device=admin_device)
            conn.rollback()
        self.live_states, self.live_actors, self.live_admin_device = states, actors, admin_device
        self.check_private_inputs()
        self.check_hold()
        return result
    def snapshot(self):
        self.check_hold()
        result = self.old.snapshot(self.native, self.backup, self.storage)
        self.check_hold()
        return result
    def service(self, action, unit):
        require(action in ('start', 'stop') and unit in self.old.UNITS, 'normal443_own_service_scope')
        self.check_hold()
        self.check(0 if getattr(self, 'rolling_back', False) else 500)
        code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\nsubprocess.run(" + repr(
            ['/usr/bin/systemctl', action, unit]) + ",check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        self.native.helper(code, 40)
    def boundary(self, release):
        self.check_hold()
        result = self.old.await_service_boundary(self.native, self.storage, release)
        proof = self.recovery.completion_unit_provenance(self.native, result)
        self.recovery.await_direct_health(release)
        result = {'units': result, 'completion_unit_provenance': proof,
                  'worker_configuration_provenance': self.native.worker_configuration(self.old.protected(APP / '.env', 65536), release, result)}
        self.check_hold()
        return result
    def foreign(self):
        self.check_hold()
        require(RECOVERY_DECL in self.buffers, 'normal443_checked_recovery_contract')
        # Retain the old declaration/history; the checked acceptance descendant
        # separately authenticates the exact current post-restoration boundary.
        declaration = self.buffers[RECOVERY_DECL]
        require(declaration == self.git(ROOT, 'show', self.served + ':' + self.recovery.DECL), 'normal443_recovery_declaration')
        policy = self.recovery.contract_from_bytes(declaration)
        current=getattr(self.acceptance,'current_external_boundary',None)
        require(callable(current),'normal443_checked_current_external_boundary')
        result = current(self.recovery,policy['external_configuration_ack'])
        self.check_hold()
        return result
    @contextmanager
    def hold(self):
        with ExitStack() as stack:
            def acquire(relative, seconds):
                with source_files.open_root(RUNTIME / Path(relative).parent) as parent:
                    fd = os.open(Path(relative).name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                stack.callback(os.close, fd)
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'normal443_existing_owned_lock')
                end = min(self.deadline, time.monotonic() + seconds)
                while True:
                    try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                    except BlockingIOError:
                        require(time.monotonic() < end, 'normal443_lock_drain_timeout'); time.sleep(.05)
                self.lock_rows.append({'path': str(RUNTIME / relative), 'fd': fd, 'device': info.st_dev, 'inode': info.st_ino})
            for relative in self.acceptance.LOCKS: acquire(relative, 30)
            policy = self.recovery.contract_from_bytes(self.buffers[RECOVERY_DECL])
            sources = self.recovery.publisher_unit_sources()
            observe = self.recovery.publisher_observer(self.backup)
            selected = self.recovery.await_natural_publication(policy, observe)
            acquire(self.acceptance.PUBLICATION_LOCK, 120)
            acquired = time.monotonic()
            current = observe()
            require(current['coherent_unit'] and all(current[name] == selected[name] for name in ('row', 'unit', 'timer', 'journal'))
                and self.recovery.publisher_unit_sources() == sources, 'normal443_selected_publication_drift')
            self.alignment = {'selected': selected, 'unit_sources': sources,
                'hold': {'acquired_monotonic': acquired, 'deadline_monotonic': self.deadline}}
            self.parent_start = self.acceptance.process_start(Path('/proc/self/stat').read_text())
            self.inside = True
            try: self.check_hold(); yield
            finally: self.inside = False; self.lock_rows = []; self.alignment = None
    def check_hold(self):
        self.check()
        require(self.inside and len(self.lock_rows) == 5
            and {row['path'] for row in self.lock_rows} == {str(RUNTIME / name) for name in (*self.acceptance.LOCKS, self.acceptance.PUBLICATION_LOCK)}
            and self.acceptance.process_start(Path('/proc/self/stat').read_text()) == self.parent_start,
            'normal443_same_five_lock_parent')
        controller = normal_controller_command(self.operations, self.source, self.mode, self.parent_pid,
            self.parent_start, self.alignment['hold']['acquired_monotonic'], self.deadline,
            parse_start=self.acceptance.process_start)
        held = self.acceptance.lock_population(Path('/proc/locks').read_text(), os.getpid())
        for row in self.lock_rows:
            info = os.fstat(row['fd'])
            with source_files.open_root(Path(row['path']).parent) as parent:
                attached = os.stat(Path(row['path']).name, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000 and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1 and (info.st_dev, info.st_ino) == (row['device'], row['inode']) == (attached.st_dev, attached.st_ino)
                and (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino) in held, 'normal443_kernel_five_locks')
        require(self.acceptance.process_start(Path('/proc/self/stat').read_text()) == self.parent_start,
                'normal443_controller_final_process_race')
        return {**controller, 'locks': [dict(row) for row in self.lock_rows],
                'same_five_kernel_locks_verified': True}
    def observe_publication(self):
        self.check_hold()
        fields = ('InvocationID', 'ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic')
        before = self.recovery.own_unit_properties(self.acceptance.PUBLISHER, fields)
        current = self.recovery.publisher_observer(self.backup)()
        after = self.recovery.own_unit_properties(self.acceptance.PUBLISHER, fields)
        require(before == after and after['InvocationID'] == current['unit']['InvocationID'], 'normal443_latest_invocation_race')
        selected = self.alignment['selected']['unit']
        end = (datetime.strptime(selected['ExecMainExitTimestamp'], '%a %Y-%m-%d %H:%M:%S UTC') + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S UTC')
        journal = self.old.command(['/usr/bin/journalctl', '-u', self.acceptance.PUBLISHER,
            '--since', selected['ExecMainStartTimestamp'], '--until', end, '-o', 'json', '--no-pager'])
        current.update(unit_monotonic={key: after[key] for key in fields if key != 'InvocationID'},
            selected_journal=[(row.get('_SYSTEMD_INVOCATION_ID'), row.get('MESSAGE')) for row in map(json.loads, journal.splitlines())],
            unit_sources=self.recovery.publisher_unit_sources())
        current['normal_controller_witness'] = self.check_hold(); return current
    def publisher_admission(self, conn, original, policy):
        args, kwargs = self.acceptance.captured_publisher_factory(self.verifier,
            self.recovery.publisher_observation_connection(conn), original, policy)
        current = self.observe_publication()
        witness = self.acceptance.held_publication_admission(self.alignment, current, time.monotonic())
        selected = self.alignment['selected']; names = self.acceptance.PUBLISHER_JUDGE_FIELDS
        require(self.acceptance.canonical_publisher_comparison(args[1]) == self.acceptance.canonical_publisher_comparison(current['row'])
            and args[2] == {key: current['unit'][key] for key in names} and args[3] == current['journal'], 'normal443_real_factory_observation')
        genuine = {key: selected['unit'][key] for key in names}
        def final(actual, row, unit, journal):
            latest = self.observe_publication()
            require(latest == current, 'normal443_final_publication_race')
            self.acceptance.held_publication_admission(self.alignment, latest, time.monotonic())
            require(self.acceptance.canonical_publisher_comparison(actual['row']) == row
                and actual['unit'] == {key: latest['unit'][key] for key in names} and actual['journal'] == latest['journal']
                and unit == genuine and journal == selected['journal'], 'normal443_real_callback_binding')
            return True
        proof = self.acceptance.publisher_final_adapter(self.verifier, final)(args[0], current['row'], genuine, selected['journal'], **kwargs)
        return {**proof, 'latest_invocation_assessment': witness, 'selected_previous_genuine_publication': selected}
    def current_private_completion(self, receipt):
        actual = self.recovery.completion_unit_provenance(self.native, receipt['units_after'])
        require(actual == receipt['completion_unit_provenance'] and sha(self.old.protected(APP/'.env',65536)) == receipt['environment_after_sha256'], 'normal443_same_private_completion_identity')
        return actual
    def installed_inventory(self, name, expected):
        """Admit only the two cited application paths after genuine publication."""
        paths = {'rebuild/core/preview_access.py', 'rebuild/quillmd/settings.py'}
        if name not in paths: return sha((APP.parent / name).read_bytes()) == expected
        self.check_hold()
        require(expected == sha(self.git(ROOT,'show',self.served+':'+name)),
                'normal443_immutable_private_inventory_path')
        with source_files.open_root(ROOT) as root:
            actual = source_files.operator_bytes(name,0o644,root)
        require(actual == self.buffers[name] == self.git(ROOT,'show',self.operations+':'+name),
                'normal443_actual_cited_normal_application_path')
        self.check_hold(); return True
    def full_preservation(self, *, completion=None, projection=None):
        import psycopg
        from psycopg.rows import dict_row
        self.check_hold()
        self.check_private_inputs()
        _, _, manifest, original = self.verifier.original_continuation_capture(self.historical_policy, datetime.now(timezone.utc))
        require(len(original) == 36 and manifest['tables']['django_session']['rows'] == 212, 'normal443_original_36_tables_212_sessions')
        columns = original['core_servicehealth']['columns']
        original_health = [row for row in self.verifier.row_mapping('core_servicehealth', original['core_servicehealth']['rows'], columns, ['id']).values() if row['key'] == b'backup']
        require(len(original_health) == 1, 'normal443_original_backup_identity')
        with psycopg.connect(**self.backup.source_options(APP, self.old.ROLES), row_factory=dict_row) as conn:
            self.acceptance.readonly_connection_flags(conn)
            publisher = self.publisher_admission(conn, original_health[0], self.historical_policy)
            with conn.cursor().copy("COPY (SELECT * FROM core_servicehealth WHERE key='backup') TO STDOUT") as stream:
                current = b''.join(bytes(chunk) for chunk in stream)
            rows = self.verifier.row_mapping('core_servicehealth', current.splitlines(keepends=True), columns, ['id'])
            require(len(rows) == 1, 'normal443_current_backup_identity')
            health = next(iter(rows.values()))
            require(self.verifier.service_health_original(health) == publisher['current_full_row'], 'normal443_full_current_backup_copy')
            conn.rollback()
        raw = self.acceptance.protected(self.acceptance.FROZEN / 'verify_installed_acceptance_v3.py')
        module = self.acceptance.verifier_adapter(raw, self.common, self.authority, self.verifier,
                                                 self.current_private_completion,
                                                 publisher_admission=self.publisher_admission)
        setattr(module, '__authenticated_source', raw)
        if completion is not None:
            require(completion['served_revision'] == self.operations
                and self.boundary(self.operations) == completion['units_after'], 'normal443_same_actual_normal_services')
            module.verify_service_identity = normal_service_verifier(module,raw,self,completion)
        if projection is not None:
            module.row_mapping = admitted_served_projection(module,projection)
        genuine_old = module.admitted_original_row
        def admitted(original_row, names, transition, table, actor, authentication):
            result = genuine_old(original_row, names, transition, table, actor, authentication)
            if table != 'core_servicehealth': return result
            require(all(health[key] == original_row[key] for key in ('id', 'created_at', 'key'))
                and self.verifier.service_health_original(health) == publisher['current_full_row'], 'normal443_only_source_adjudicated_backup_progress')
            return dict(health)
        module.admitted_original_row = admitted
        verify, _ = memory_verifier(module, installed_inventory=self.installed_inventory if completion is not None else None)
        report = verify(types.SimpleNamespace(progress=str(self.acceptance.CAMPAIGN / 'progress.json'), output=None))
        self.check_private_inputs()
        self.check_hold()
        require(report['complete'] is True and report['provider_calls'] == report['database_writes'] == 0
            and report['served_revision'] == self.served, 'normal443_complete_original_and_new_campaign_verification')
        # This is a new read-only report, not the immutable private receipt.
        # Its admitted backup progress must not inherit the old report's false
        # claim that no further health publication was admitted.
        report['preservation'] = {**report['preservation'], 'new_health_publications_admitted': True,
            'health_publication_admission': 'complete current row independently source-adjudicated against original identity'}
        return {'private_workflow_report': report, 'current_source_adjudicated_backup': publisher,
                'private_acceptance_sha256': sha(self.inputs['private_acceptance'][1]),
                'original_capture_replaced': False, 'current_population_guard_is_not_a_new_historical_baseline': True}
    def ingress(self):
        path = Path(INGRESS)
        with source_files.open_root(path.parent) as fd:
            leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                info = os.fstat(leaf)
                require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o644
                    and info.st_nlink == 1 and not os.listxattr(leaf), 'normal443_public_ingress_metadata')
                raw = source_files.bytes_at(leaf, 128*1024)
                again = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                require(source_files.stable(info) == source_files.stable(again), 'normal443_public_ingress_race')
                return raw, {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
                             'device': info.st_dev, 'inode': info.st_ino, 'sha256': sha(raw)}
            finally: os.close(leaf)
    def replace_ingress(self, original, candidate, metadata):
        self.check_hold()
        require(type(original) is bytes and type(candidate) is bytes and 0 < len(candidate) <= 128 * 1024
            and set(metadata) == {'uid', 'gid', 'mode', 'device', 'inode', 'sha256'}
            and metadata['uid'] == metadata['gid'] == 0 and metadata['mode'] == 0o644
            and metadata['sha256'] == sha(original), 'normal443_ingress_helper_inputs')
        # The helper has one writable mount, exactly this nginx directory. It
        # changes one fixed file and never grants writes to any co-tenant path.
        code = """import os,stat,json,hashlib,base64,subprocess
root=os.open('/target',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
os.chroot('/host');os.chdir('/')
name='quillmd';temporary='.quillmd-owner-normal443-v1-candidate'
expected=EXPECTED
replacement=base64.b64decode(REPLACEMENT)
def digest(v):return hashlib.sha256(v).hexdigest()
def current():
 f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root)
 try:
  i=os.fstat(f);assert stat.S_ISREG(i.st_mode) and i.st_nlink==1 and not os.listxattr(f)
  raw=os.read(f,131073);assert len(raw)==i.st_size<=131072
  m={'uid':i.st_uid,'gid':i.st_gid,'mode':stat.S_IMODE(i.st_mode),'device':i.st_dev,'inode':i.st_ino,'sha256':digest(raw)}
  assert os.stat(name,dir_fd=root,follow_symlinks=False).st_ino==i.st_ino
  return raw,m
 finally:os.close(f)
old,m=current();assert m==expected and m['uid']==m['gid']==0 and m['mode']==420
assert digest(old)==ORIGINAL_SHA
f=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,420,dir_fd=root)
try:
 os.fchmod(f,420);assert os.write(f,replacement)==len(replacement);os.fsync(f)
 assert current()[1]==expected
 os.replace(temporary,name,src_dir_fd=root,dst_dir_fd=root);os.fsync(root)
finally:
 os.close(f)
 try:os.unlink(temporary,dir_fd=root)
 except FileNotFoundError:pass
subprocess.run(['/usr/sbin/nginx','-t'],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['/usr/bin/systemctl','reload','nginx.service'],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
raw,m=current();assert digest(raw)==digest(replacement)
print(json.dumps(m,sort_keys=True))
""".replace('EXPECTED', repr(metadata)).replace('REPLACEMENT', repr(base64.b64encode(candidate))).replace('ORIGINAL_SHA', repr(sha(original)))
        argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none', '--pid=host',
            '--mount', 'type=bind,src=/,dst=/host,readonly', '--mount', 'type=bind,src=/etc/nginx/sites-available,dst=/target',
            self.managed.IMAGE, 'python', '-B', '-']
        result = json.loads(self.managed.run_helper(argv, input=code.encode(), timeout=60,
                                                  failure_directory=OUTPUT).stdout)
        self.check_hold()
        return result
    def forward(self, target):
        self.check_hold()
        result = subprocess.run(['git', '-C', str(ROOT), 'merge', '--ff-only', target], capture_output=True, timeout=30, umask=0o022)
        require(result.returncode == 0 and self.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == target
            and not self.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'normal443_source_fast_forward')
        self.recovery.source_readability(ROOT)
    def write(self, name, value):
        raw = value if isinstance(value, bytes) else encode(value)+b'\n'
        path = ATTEMPT if name == 'attempt' else OUTPUT / name
        with source_files.open_root(path.parent) as parent:
            fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    def routes(self):
        import httpx
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as client:
            statuses = {}
            for origin, expected in (('https://app.quillmd.com',503), ('https://admin.quillmd.com',503),
                                      ('https://quillmd.com',200), ('https://www.quillmd.com',200), ('https://pro.quillmd.com',410)):
                self.check_hold()
                response = client.get(origin+'/', headers={'Cookie':''})
                require(response.status_code == expected, 'normal443_anonymous_or_cotenant_http')
                if expected == 503:
                    require(response.headers.get('retry-after') == '3600' and response.headers.get('cache-control') == 'no-store', 'normal443_maintenance_headers')
                statuses[origin] = response.status_code
            self.check_hold()
            return statuses

    def copy_population(self):
        """Read the complete current COPY population into memory; never recapture history."""
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
        self.check_hold(); result = {}
        with psycopg.connect(**self.backup.source_options(APP,self.old.ROLES),row_factory=dict_row) as conn:
            self.acceptance.readonly_connection_flags(conn)
            conn.execute("SET LOCAL timezone='UTC'"); conn.execute("SET LOCAL datestyle='ISO, MDY'")
            query=lambda statement:[tuple(row.values()) for row in conn.execute(statement).fetchall()]
            keys=self.backup.table_queries(query)
            require(set(keys)==SERVED_TABLES,'normal443_served_exact_current_36_tables')
            for table,primary_keys in keys.items():
                columns=[row['column_name'] for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(table,)).fetchall()]
                statement=sql.SQL('COPY (SELECT * FROM public.{} ORDER BY {}) TO STDOUT').format(
                    sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,primary_keys)))
                with conn.cursor().copy(statement) as stream: raw=b''.join(bytes(chunk) for chunk in stream)
                result[table]={'columns':columns,'primary_keys':list(primary_keys),'rows':raw.splitlines(keepends=True)}
            conn.rollback()
        served_copy_tables(result); self.check_hold(); return result

    def check_verification_directory(self):
        with source_files.open_root(VERIFY_OUTPUT) as directory:
            observed=os.fstat(directory)
            require((observed.st_dev,observed.st_ino,observed.st_uid,observed.st_gid,stat.S_IMODE(observed.st_mode))
                ==self.served_directory_identity,'normal443_same_owned_verification_directory')

    def verify_write(self,name,value):
        require(name=='STOP.json' or re.fullmatch(r'[a-z0-9-]+\.(?:json|log|fernet)',name or '') is not None,
                'normal443_fixed_verification_leaf')
        raw=value if isinstance(value,bytes) else encode(value)+b'\n'
        require(len(raw)<=16*1024*1024,'normal443_verification_evidence_bound')
        self.check_verification_directory()
        path=VERIFY_ATTEMPT if name=='attempt.json' else VERIFY_OUTPUT/name
        with source_files.open_root(path.parent) as parent:
            if path.parent==VERIFY_OUTPUT:
                observed=os.fstat(parent)
                require((observed.st_dev,observed.st_ino,observed.st_uid,observed.st_gid,stat.S_IMODE(observed.st_mode))
                    ==self.served_directory_identity,'normal443_same_owned_verification_directory')
            fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            with os.fdopen(fd,'wb') as stream:
                os.fchmod(stream.fileno(),0o600);observed=os.fstat(stream.fileno())
                require(stat.S_ISREG(observed.st_mode) and observed.st_uid==observed.st_gid==1000
                    and observed.st_nlink==1 and not os.listxattr(stream.fileno()),'normal443_owned_verification_evidence')
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.fsync(parent)
        self.check_verification_directory()

    def authenticated_gets(self,states):
        """Exactly two API requests; no browser, subresources, redirects, retry or login."""
        self.check_hold()
        self.check_verification_directory()
        code=r"""import fs from 'node:fs';import {createRequire} from 'node:module';import crypto from 'node:crypto';
const {request}=createRequire('/opt/meddoc-pro/package.json')('@playwright/test');
const input=JSON.parse(fs.readFileSync(0,'utf8'));const output={complete:false,attempts:[]};
const must=(value,label)=>{if(!value)throw new Error(label)};const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
try{for(const [actor,path,markers] of [['doctor','/',['Clinical workspace','A little less paperwork.']],['admin','/console/services/',['Administration','Workspace health.','Release',input.target]]]){
 let ctx;const item={actor,path,started_at:new Date().toISOString(),GET_requests:0};output.attempts.push(item);
 try{ctx=await request.newContext({storageState:input.states[actor],ignoreHTTPSErrors:false,timeout:15000});
  item.before=await ctx.storageState();const url='https://app.quillmd.com'+path;item.GET_requests=1;
  const response=await ctx.get(url,{maxRedirects:0,maxRetries:0,timeout:15000,failOnStatusCode:false});
  item.status=response.status();item.url=response.url();const body=await response.body();must(body.length<=2097152,'bounded served HTML');
  item.body_sha256=sha(body);item.after=await ctx.storageState();const text=body.toString('utf8');
  must(item.status===200&&item.url===url&&(response.headers()['content-type']||'').includes('text/html'),'exact authenticated dashboard response');
  must(markers.every(value=>text.includes(value))&&!text.includes('name="password"'),'actual protected dashboard markers');item.markers_verified=true;
 }finally{if(ctx)await ctx.dispose();item.finished_at=new Date().toISOString();}
}output.complete=true;}catch{output.failure='normal443_authenticated_served_GET_failed_or_unknown';}
console.log(JSON.stringify(output));if(!output.complete)process.exitCode=2;
"""
        self.check_verification_directory()
        self.acceptance.child_process(['/usr/bin/node','--input-type=module','-e',code],self.source,VERIFY_OUTPUT,
            'served-get',min(self.forward_deadline,time.monotonic()+60),ruled=False,
            environment={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin'},input_bytes=encode({'states':states,'target':self.operations}),
            writer=lambda path,raw:self.verify_write(Path(path).name,raw))
        self.check_verification_directory()
        report=json.loads(source_files.protected(VERIFY_OUTPUT/'served-get-stdout.log'))
        require(report.get('complete') is True and len(report.get('attempts',[]))==2
            and [item.get('actor') for item in report['attempts']]==['doctor','admin'],
            'normal443_complete_two_served_GETs')
        self.check_hold(); return report

def population_fingerprints(population):
    return {table:{'rows':len(item['rows']),'sha256':sha(b''.join(item['rows']))} for table,item in population.items()}

def guard_with_admitted_served_changes(before,after,before_rows,after_rows,admission):
    require(before['database']['tables']==population_fingerprints(before_rows)
        and after['database']['tables']==population_fingerprints(after_rows),
        'normal443_complete_COPY_and_snapshot_same_population')
    require(admission['new_session_keys']==0 and admission['session_rows_changed']<=4
        and admission['audit_addition']['action']=='admin.services_read', 'normal443_exact_served_delta_guard')
    projected=copy.deepcopy(after)
    for table in ('django_session','core_auditevent'):
        projected['database']['tables'][table]=copy.deepcopy(before['database']['tables'][table])
    compare_guard(before,projected)
    return True

def served_projection(before,after,verifier):
    return {'columns':{table:after[table]['columns'] for table in ('django_session','core_auditevent')},
        'primary_keys':{table:after[table]['primary_keys'] for table in ('django_session','core_auditevent')},
        'post_populations':{table:verifier.row_mapping(table,after[table]['rows'],after[table]['columns'],after[table]['primary_keys'])
            for table in ('django_session','core_auditevent')},
        'projected_populations':{table:verifier.row_mapping(table,before[table]['rows'],before[table]['columns'],before[table]['primary_keys'])
            for table in ('django_session','core_auditevent')}}

def verify_served(host,policy,target):
    require(SERVED_VERIFICATION_PROTOCOL_QUALIFIED,'normal443_served_verification_protocol_unqualified')
    require(not os.path.lexists(VERIFY_OUTPUT) and not os.path.lexists(VERIFY_ATTEMPT),
            'normal443_single_served_verification_attempt')
    completion,completion_raw=normal_completion(policy,target)
    host.served_request_attempted=False
    created=False
    try:
        with source_files.open_root(VERIFY_OUTPUT.parent) as directory:
            os.mkdir(VERIFY_OUTPUT.name,0o700,dir_fd=directory);created=True
            observed=os.stat(VERIFY_OUTPUT.name,dir_fd=directory,follow_symlinks=False)
            host.served_directory_identity=(observed.st_dev,observed.st_ino,observed.st_uid,observed.st_gid,stat.S_IMODE(observed.st_mode))
            require(stat.S_ISDIR(observed.st_mode) and observed.st_uid==observed.st_gid==1000
                and stat.S_IMODE(observed.st_mode)==0o700,'normal443_owned_verification_directory')
            os.fsync(directory)
        return _verify_served(host,policy,target,completion,completion_raw)
    except BaseException as error:
        # A collision is not our evidence directory. Never put STOP into it.
        # Once our exclusive mkdir succeeded, even its parent fsync failure
        # belongs to this single attempt and must enter the retained stop path.
        if not created:raise
        host.rolling_back=True
        reason=str(error) if isinstance(error,Refusal) and re.fullmatch('normal443_[a-z0-9_]+',str(error)) else None
        host.verify_write('STOP.json',{'complete':False,'current_served_revision':target,
            'request_attempt_started':host.served_request_attempted,'failure_kind':type(error).__name__,'failure_reason':reason,
            'GET_outcomes':'unknown unless retained response logs and renewal observations establish them',
            'clinical_writes':0,'authentication_submissions':0,'provider_calls':0,'automatic_retries':False,
            'normal_availability_left_in_place':True,'session_and_audit_records_preserved':True})
        raise Refusal('normal443_served_verification_stopped_preserving_records') from None

def _verify_served(host,policy,target,completion,completion_raw):
    with host.hold():
        require(host.git(ROOT,'rev-parse','HEAD').strip().decode()==target
            and host.git(ROOT,'branch','--show-current').strip()==b'main'
            and not host.git(ROOT,'status','--porcelain','--untracked-files=no').strip(), 'normal443_exact_installed_normal_source')
        require(host.boundary(target)==completion['units_after'],'normal443_actual_normal_completion_native_identity')
        original=host.cipher.decrypt(source_files.protected(OUTPUT/'environment-before.fernet'))
        enabled=host.cipher.decrypt(source_files.protected(OUTPUT/'environment-enabled.fernet'))
        require(enabled==controlled_environment(original,policy['private_accepted_revision'],target,enabled=True)
            and host.old.protected(APP/'.env',65536)==enabled,'normal443_exact_completed_normal_environment')
        ingress,metadata=host.ingress()
        require(metadata==completion['ingress_after'] and sha(ingress)==completion['candidate_sha256'],
                'normal443_actual_completed_normal_ingress')
        foreign=host.foreign(); before=host.snapshot(); before_rows=host.copy_population()
        require(before['database']['tables']==population_fingerprints(before_rows),'normal443_pre_GET_population_binding')
        full_before=host.full_preservation(completion=completion)
        compare_guard(before,host.snapshot())
        host.forward_budget(); live_before=host.session_admission(SESSION_FORWARD_RESERVE)
        states=copy.deepcopy(host.live_states); actors=dict(host.live_actors)
        keys={actor:{kind:next(c['value'] for c in state['cookies'] if c['name']==name)
            for kind,name in (('normal','quillmd_doctor_session'),('preview','__Host-quillmd_preview'))}
            for actor,state in states.items()}
        compare_guard(before,host.snapshot())
        host.verify_write('prepared.json',{'format':1,'complete':False,'normal_completion_sha256':sha(completion_raw),
            'current_served_revision':target,'private_workflow_revision':policy['private_accepted_revision'],
            'live_session_admission':live_before,'original_capture_replaced':False,
            'authentication_submissions':0,'provider_calls':0,'clinical_writes':0,'automatic_retries':False})
        host.verify_write('before-proof.json',full_before)
        host.verify_write('attempt.json',{'format':1,'attempt':1,'normal_completion_sha256':sha(completion_raw),
            'current_served_revision':target,'GET_requests_maximum':2,'authentication_submissions':0,
            'provider_calls':0,'automatic_retries':False})
        host.served_request_attempted=True; browser=host.authenticated_gets(states)
        intervals={}; following={}
        for item in browser['attempts']:
            actor=item['actor'];begin=datetime.fromisoformat(item['started_at'].replace('Z','+00:00'))
            end=datetime.fromisoformat(item['finished_at'].replace('Z','+00:00'))
            require(item['GET_requests']==1 and 0<=(end-begin).total_seconds()<=60
                and item['before']==states[actor], 'normal443_genuine_single_GET_capture_interval')
            intervals[actor]=(begin,end);following[actor]=item['after']
            host.verify_write(actor+'-state-before.json',item['before']);host.verify_write(actor+'-state-after.json',item['after'])
        after_rows=host.copy_population();after=host.snapshot()
        admission=admit_served_deltas(before_rows,after_rows,keys,actors,intervals,
            host.session_secret,host.preview_fingerprint,host.verifier)
        guard_with_admitted_served_changes(before,after,before_rows,after_rows,admission)
        # Raw full COPY populations stay in memory. Retain only the four
        # measured session pairs and new audit row inside encrypted custody.
        observed={}
        for table in ('django_session','core_auditevent'):
            selected = {value.encode() for item in keys.values() for value in item.values()} if table=='django_session' else {admission['audit_addition']['id'].encode()}
            position=after_rows[table]['columns'].index('session_key' if table=='django_session' else 'id')
            observed[table]={'columns':after_rows[table]['columns'],**{kind+'_rows':[
                base64.b64encode(row).decode() for row in population[table]['rows']
                if row[:-1].split(b'\t')[position] in selected]
                for kind,population in (('before',before_rows),('after',after_rows))}}
        host.verify_write('renewal-observations.fernet',host.cipher.encrypt(encode(observed)))
        projected=served_projection(before_rows,after_rows,host.verifier)
        full_after=host.full_preservation(completion=completion,projection=projected)
        compare_guard(after,host.snapshot())
        require(normal_completion(policy,target)[1]==completion_raw,'normal443_normal_completion_inputs_unchanged')
        require(host.foreign()==foreign and host.boundary(target)==completion['units_after'],
                'normal443_post_GET_native_and_foreign_preserved')
        indexed=served_copy_tables(after_rows)['django_session']
        actual_sessions={key[0].decode():{'session_key':key[0].decode(),
            'session_data':host.verifier.copy_value(row[1]['session_data']).decode(),
            'expire_date':host.verifier.parsed_timestamp(row[1]['expire_date'])}
            for key,row in indexed.items() if key[0].decode() in {value for item in keys.values() for value in item.values()}}
        live_after=live_session_admission(following,actual_sessions,actors,host.session_secret,
            host.preview_fingerprint,host.verifier.normal_session,datetime.now(timezone.utc),SESSION_COMPLETION_RESERVE,
            admin_device=host.live_admin_device)
        host.check_hold()
        report={'format':1,'complete':True,'current_served_revision':target,
            'private_workflow_revision':policy['private_accepted_revision'],'normal_completion_sha256':sha(completion_raw),
            'authenticated_GETs':[{'actor':item['actor'],'path':item['path'],'status':item['status'],
                'started_at':item['started_at'],'finished_at':item['finished_at'],'body_sha256':item['body_sha256'],
                'markers_verified':item['markers_verified']} for item in browser['attempts']],
            'session_rows_updated':admission['session_rows_changed'],'new_session_rows':0,
            'audit_rows_added':1,'audit_addition':admission['audit_addition'],'SQL_statement_count':'not_instrumented',
            'session_renewals':admission['session_renewals'],'clinical_writes':0,'authentication_submissions':0,
            'provider_calls':0,'automatic_retries':False,'original_capture_replaced':False,
            'post_GET_full_original_and_private_campaign_proof':full_after,
            'session_admission_projection':'Only independently admitted four renewals and one audit addition projected to the actual pre-GET population; original capture and campaign intervals unchanged.',
            'live_session_admission_after':live_after,'completion_valid_only_without_STOP':True}
        host.verify_write('complete.json',report);host.check_hold()
        return {'complete':True,'application_url':'https://app.quillmd.com/',
            'admin_url':'https://app.quillmd.com/console/services/','served_revision':target,
            'private_workflow_revision':policy['private_accepted_revision'],'authenticated_GETs':2,
            'session_rows_updated':admission['session_rows_changed'],'audit_rows_added':1,
            'new_session_rows':0,'clinical_writes':0,'authentication_submissions':0,'provider_calls':0}

def transition(host, policy, target, buffers, *, execute=False):
    require(type(buffers) is dict and TEMPLATE in buffers, 'normal443_checked_template_buffer')
    require(not os.path.lexists(OUTPUT) and not os.path.lexists(ATTEMPT), 'normal443_single_consumable_attempt')
    with host.hold():
        host.check(500)
        require(host.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == policy['private_accepted_revision']
            and host.git(ROOT, 'branch', '--show-current').strip() == b'main'
            and not host.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'normal443_exact_prior_served_source')
        before = host.snapshot()
        require(before['database']['pending_jobs'] == before['database']['held'] == 0, 'normal443_idle_current_population')
        private = host.full_preservation()
        # Bind the complete verifier to the same observed transition population.
        # The input locks do not prevent an owner/browser from writing an old
        # row between verification and the guard capture.
        compare_guard(before, host.snapshot())
        sessions = host.session_admission(SESSION_FORWARD_RESERVE)
        compare_guard(before, host.snapshot())
        foreign = host.foreign()
        original, metadata = host.ingress()
        require(before['configuration'][INGRESS] == metadata
            and metadata == policy['original_ingress_metadata']
            and before['configuration'][PRIVATE_INGRESS]['sha256'] == PRIVATE_INGRESS_SHA
            and before['configuration'][str(ROOT/'Caddyfile')]['sha256'] == CADDY_SHA, 'normal443_ingress_and_caddy_boundary')
        candidate = render_ingress(original, buffers[TEMPLATE])
        prior = policy['private_accepted_revision']
        updated = controlled_environment(host.original_environment, prior, target, enabled=True)
        disabled = controlled_environment(host.original_environment, prior, target, enabled=False)
        own = host.boundary(prior)
        compare_guard(before, host.snapshot())
        require(host.foreign() == foreign, 'normal443_foreign_initial_race')
        if not execute:
            return {'complete':True,'read_only_preflight':True,'execution_performed':False,
                'candidate_sha256':sha(candidate),'full_original_and_new_acceptance_population_reverified':True,
                'private_acceptance_admitted':True,'live_session_admission':sessions,
                'original_capture_replaced':False,'provider_calls':0,'authentication_submissions':0,'database_writes':0}
        host.check(500)
        OUTPUT.mkdir(mode=0o700)
        prepared = {'format':1,'complete':False,'protocol':'owner-normal443-active-source-v1', 'previous_served_revision':prior,
            'served_revision':target,'private_acceptance_sha256':private['private_acceptance_sha256'],
            'preservation':private,'guard_before':before,'foreign_before':foreign,'units_before':own,
            'private_acceptance_admitted':True,'live_session_admission_before':sessions,
            'candidate_sha256':sha(candidate),'original_ingress_metadata':metadata,'provider_calls':0,
            'authentication_submissions':0,'database_writes':0,'original_capture_replaced':False,'automatic_retries':False}
        forwarded = False; ingress_helper_completed = False; mutation_started = False
        try:
            host.write('environment-before.fernet',host.cipher.encrypt(host.original_environment))
            host.write('environment-enabled.fernet',host.cipher.encrypt(updated))
            host.write('environment-disabled.fernet',host.cipher.encrypt(disabled))
            host.write('original-ingress.conf',original); host.write('prepared.json',prepared)
            compare_guard(before, host.snapshot()); host.check(500)
            require(host.foreign() == foreign, 'normal443_foreign_before_marker_race')
            # Start the forward budget before the last live-session read. Its
            # database observation and following guard capture consume that
            # budget rather than introducing an unmeasured expiry gap.
            host.forward_budget()
            sessions = host.session_admission(SESSION_FORWARD_RESERVE)
            compare_guard(before, host.snapshot())
            host.write('live-sessions-before.json',sessions)
            host.write('attempt',{'format':1,'attempt':1,'served_revision':target,'output':str(OUTPUT),'provider_calls':0,'authentication_submissions':0,'automatic_retries':False})
            mutation_started = True
            for unit in reversed(host.old.UNITS): host.service('stop',unit)
            compare_guard(before, host.snapshot())
            host.forward(target); forwarded = True
            host.env_writer.replace_environment(APP/'.env',host.original_environment,updated)
            for unit in host.old.UNITS: host.service('start',unit)
            active = host.boundary(target)
            compare_guard(before, host.snapshot())
            require(host.foreign() == foreign, 'normal443_foreign_post_start_race')
            host.check(500)
            new_metadata = host.replace_ingress(original,candidate,metadata); ingress_helper_completed = True
            compare_guard(before, host.snapshot(), ingress=new_metadata)
            statuses = host.routes()
            compare_guard(before, host.snapshot(), ingress=new_metadata)
            require(host.foreign() == foreign and host.boundary(target) == active, 'normal443_final_source_or_foreign_race')
            compare_guard(before, host.snapshot(), ingress=new_metadata)
            # No potentially lengthy population capture follows this fresh
            # TTL observation. Retain its completion reserve for evidence I/O.
            final_sessions = host.session_admission(SESSION_COMPLETION_RESERVE)
            host.check_hold()
            completed = {**prepared,'complete':True,'stage':'complete','units_after':active,'ingress_after':new_metadata,
                'anonymous_http_statuses':statuses,'owner_normal_origin_enabled':True,'preview_origin':'https://app.quillmd.com:9443',
                'normal_origin':'https://app.quillmd.com','full_original_and_new_acceptance_population_preserved':True,
                'actual_provider_model_reverified_by_this_transition':False,'workflow_byte_identity_inherited_from_private_acceptance':True}
            completed['live_session_admission_after'] = final_sessions
            completed['session_renewal_performed'] = False
            completed['completion_valid_only_without_failed_receipt'] = True
            host.write('complete.json',completed)
            # Durable evidence I/O also consumes the forward interval. An I/O
            # stall must enter the measured failure/rollback path rather than
            # returning success with expired grants. Preserve both receipts.
            host.check_hold()
            return {'complete':True,'application_url':'https://app.quillmd.com/','private_origin':'https://app.quillmd.com:9443',
                'served_revision':target,'restricted_to_existing_owner_grants':True,'provider_calls':0,'authentication_submissions':0,'database_writes':0}
        except BaseException as error:
            reason = str(error) if isinstance(error, Refusal) and re.fullmatch('normal443_[a-z0-9_]+', str(error)) else None
            if not mutation_started:
                host.write('failed.json',{**prepared,'stage':'preparation_failed','failure_kind':type(error).__name__,
                    'failure_reason':reason,'mutation_started':False,'service_actions':0,'ingress_actions':0,'automatic_retries':False})
                raise Refusal('normal443_preparation_failed_preserving_availability') from None
            host.rolling_back = True
            rollback = {'attempted':True,'source_reset':False,'provider_calls':0,'authentication_submissions':0,
                        'ingress_observed_before_rollback': 'unassessed'}
            try:
                actual_revision = host.git(ROOT, 'rev-parse', 'HEAD').strip().decode()
                require(actual_revision in (prior, target)
                    and host.git(ROOT, 'branch', '--show-current').strip() == b'main'
                    and not host.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(),
                    'normal443_rollback_known_source')
                # A successful merge can be followed by a failed read-through
                # or interrupted return. Decide from actual HEAD, never from
                # whether the forward method happened to return to this caller.
                forwarded = actual_revision == target
                current, current_metadata = host.ingress()
                rollback['ingress_observed_before_rollback'] = current_metadata
                if sha(current) == sha(candidate):
                    restored = host.replace_ingress(current,original,current_metadata)
                else:
                    require(current == original, 'normal443_rollback_unknown_ingress'); restored = current_metadata
                for unit in reversed(host.old.UNITS): host.service('stop',unit)
                environment = host.old.protected(APP/'.env',65536)
                if forwarded:
                    require(environment in (host.original_environment,updated,disabled), 'normal443_rollback_unknown_environment')
                    if environment != disabled:host.env_writer.replace_environment(APP/'.env',environment,disabled)
                    release = target
                else:
                    require(environment == host.original_environment, 'normal443_rollback_pre_forward_environment');release = prior
                for unit in host.old.UNITS:host.service('start',unit)
                rollback['units'] = host.boundary(release)
                compare_guard(before, host.snapshot(), ingress=restored)
                require(host.foreign() == foreign, 'normal443_rollback_foreign_preservation')
                rollback.update(complete=True,private_availability_preserved=True,owner_normal_origin_enabled=False,served_revision=release,ingress=restored)
            except BaseException:
                rollback.update(complete=False,private_availability_preserved=False,fail_stop=host.old.best_effort_private_stop(host.native))
            host.write('failed.json',{**prepared,'stage':'failed','failure_kind':type(error).__name__,'failure_reason':reason,'rollback':rollback,
                'ingress_helper_completed_before_failure':ingress_helper_completed,'automatic_retries':False})
            raise Refusal('normal443_failed_with_preserved_evidence') from None

def main(argv=None, *, host=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--operations-revision')
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--preflight',action='store_true');mode.add_argument('--execute',action='store_true')
    mode.add_argument('--verify-served',action='store_true')
    args=parser.parse_args(argv)
    if not (args.preflight or args.execute or args.verify_served):
        print(json.dumps({'execution_performed':False,'installed_state_accessed':False,'active_protocol_qualified':ACTIVE_PROTOCOL_QUALIFIED,
            'private_acceptance_protocol_qualified':PRIVATE_ACCEPTANCE_PROTOCOL_QUALIFIED,
            'private_acceptance_completed':False,'ingress_publication_qualified':INGRESS_PUBLICATION_QUALIFIED,
            'served_verification_protocol_qualified':SERVED_VERIFICATION_PROTOCOL_QUALIFIED,
            'served_authenticated_verification_completed':False,
            'provider_calls':0,'authentication_submissions':0,'database_writes':0,'automatic_retries':False},sort_keys=True));return 0
    if args.verify_served:require(SERVED_VERIFICATION_PROTOCOL_QUALIFIED,'normal443_served_verification_protocol_unqualified')
    started=time.monotonic();policy,buffers=source_gate(args.operations_revision)
    host=host if host is not None else NativeHost(policy,args.operations_revision,buffers,started,
                                                mode='--verify-served' if args.verify_served else ('--execute' if args.execute else '--preflight'))
    result=verify_served(host,policy,args.operations_revision) if args.verify_served else transition(host,policy,args.operations_revision,buffers,execute=args.execute)
    print(json.dumps(result,sort_keys=True));return 0 if result['complete'] else 2
