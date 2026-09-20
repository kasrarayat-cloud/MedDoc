#!/usr/bin/env python3
"""Prepaid account-audit handoff and fail-closed import. No provider credential or network I/O.

An operator must run the portable collector outside the worker with separate
account-wide read-only access. This is deliberately not an unattended renewal.
"""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import secrets

try:
    from . import automatic_offsite as engine, offsite_allocation as allocation
    from . import offsite_account_audit as collector, install_offsite_policy as installer
except ImportError:
    import automatic_offsite as engine
    import offsite_allocation as allocation
    import offsite_account_audit as collector
    import install_offsite_policy as installer

STATE = engine.STATE / 'renewal'
ACCOUNT_ID = '53c8a3000a96'  # Nonsecret identity pinned by the original owner account audit.
REASONS = {'audit_access_unavailable', 'audit_failed', 'ticket_expired', 'ticket_invalid',
           'evidence_invalid', 'policy_conflict', 'publication_failed', 'budget_exhausted', 'state_invalid'}


class Refusal(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise Refusal(code)


def state_directory():
    return engine.backup.private_dir(STATE, create=True)


def read_state():
    path = STATE / 'status.json'
    if not path.exists() and not path.is_symlink():
        return {'state': 'never_requested', 'reason_code': 'audit_access_unavailable', 'ticket_id': None}
    value = json.loads(engine.offsite.read_private(path, 16384))
    require(value.get('state') in ('awaiting_external_audit', 'importing', 'failed', 'installed')
            and value.get('reason_code') in REASONS | {None}
            and re.fullmatch('[a-f0-9]{32}', value.get('ticket_id', '')), 'state_invalid')
    return value


def renewal_status(at=None):
    """Safe local display; never grants admission or changes the previous observation."""
    at = at or engine.now()
    value = read_state()
    policy, _ = historical_limits()
    state = value['state']
    reason = value.get('reason_code')
    if state == 'awaiting_external_audit' and at >= engine.timestamp(value['ticket_valid_until']):
        state, reason = 'failed', 'ticket_expired'
    return {'state': state, 'last_attempt_at': value.get('last_attempt_at'),
            'last_successful_observation_at': policy['observed_at'], 'valid_until': policy['valid_until'],
            'reason_code': reason, 'ticket_id': value.get('ticket_id'),
            'unattended_available': False, 'required_access': 'separate_account_wide_read_only_audit',
            'failure_does_not_extend_validity': True}


def historical_limits():
    """Expiry forbids backup work, not a separately prepaid read-only repair audit.

    Validate every original control and the actual policy at its ORIGINAL time;
    never pass this historical policy to the network worker or extend its expiry.
    """
    raw = engine.offsite.read_private(engine.POLICY, 16384)
    value = json.loads(raw)
    return engine.policy(engine.POLICY, engine.timestamp(value['observed_at'])), raw


def reservation_binding(ticket, ticket_bytes, ledger):
    require(re.fullmatch('[a-f0-9]{32}', ticket.get('ticket_id', '')), 'ticket_invalid')
    canonical = engine.offsite.read_private(STATE / (ticket['ticket_id'] + '.ticket.json'), 16384)
    require(canonical == ticket_bytes, 'ticket_invalid')
    entries = [row for row in ledger.get('external_reservations', [])
               if row.get('reference') == ticket['reservation_reference']]
    day = engine.timestamp(ticket['not_before']).strftime('%Y-%m-%d')
    require(len(entries) == 1 and entries[0]['requests'] == ticket['request_limit']
            and entries[0]['download_bytes'] == ticket['response_byte_limit']
            and entries[0]['charged_days'] == [day], 'ticket_invalid')
    totals = ledger.get('days', {}).get(day, {})
    require(totals.get('requests', -1) >= ticket['request_limit']
            and totals.get('download_bytes', -1) >= ticket['response_byte_limit'], 'ticket_invalid')


def issue_ticket(start, end, commit, *, at=None):
    at = at or engine.now()
    require(re.fullmatch('[a-f0-9]{40}', commit), 'ticket_invalid')
    start, end = engine.timestamp(start), engine.timestamp(end)
    with engine.exclusion(engine.STATE):
        limits, prior = historical_limits()
        require(at <= start < end <= at + timedelta(days=2), 'ticket_invalid')
        previous = read_state()
        require(previous['state'] != 'importing', 'state_invalid')
        if previous['state'] == 'awaiting_external_audit':
            require(at >= engine.timestamp(previous['ticket_valid_until']), 'ticket_invalid')
        ticket_id = secrets.token_hex(16)
        ticket = dict(version=1, kind='quillmd-account-audit-reservation', ticket_id=ticket_id,
                      account_id=ACCOUNT_ID, bucket_id=limits['bucket_id'], prefix=limits['prefix'],
                      issued_at=at.isoformat(), not_before=start.isoformat(), valid_until=end.isoformat(),
                      request_limit=20, response_byte_limit=8 * 1024 * 1024, max_run_seconds=300,
                      reservation_reference='account-audit-' + ticket_id, source_revision=commit,
                      collector_source_sha256=installer.digest(Path(collector.__file__).read_bytes()),
                      expected_policy_sha256=installer.digest(prior))
        collector.validate_ticket(ticket, start)
        day = start.strftime('%Y-%m-%d')
        journal = engine.budget_ledger(engine.STATE / 'budget.json', at)
        counter = journal['days'].setdefault(day, {'requests': 0, 'download_bytes': 0})
        require(counter['requests'] + ticket['request_limit'] <= limits['daily_request_budget']
                and counter['download_bytes'] + ticket['response_byte_limit'] <= limits['daily_download_budget_bytes'],
                'budget_exhausted')
        state_directory()
        raw = installer.encoded(ticket)
        engine.backup.write_private(STATE / (ticket_id + '.intent.json'), installer.encoded({
            'ticket': ticket, 'ledger_sha256_before': installer.digest(installer.encoded(journal)),
            'created_at': at.isoformat(), 'no_refunds': True}))
        counter['requests'] += ticket['request_limit']
        counter['download_bytes'] += ticket['response_byte_limit']
        journal['external_reservations'].append(dict(reference=ticket['reservation_reference'], at=at.isoformat(),
            requests=ticket['request_limit'], download_bytes=ticket['response_byte_limit'], charged_days=[day]))
        current = journal['days'].get(journal['day'], {'requests': 0, 'download_bytes': 0})
        journal.update(**current)
        # Durability order matters: a crash can strand a PAID ticket, never publish a free one.
        engine.atomic(engine.STATE / 'budget.json', journal)
        engine.backup.write_private(STATE / (ticket_id + '.ticket.json'), raw)
        installer.fsync_directory(STATE)
        engine.atomic(STATE / 'status.json', dict(state='awaiting_external_audit', ticket_id=ticket_id,
            reason_code='audit_access_unavailable', last_attempt_at=at.isoformat(), ticket_valid_until=end.isoformat()))
        return {'ticket_path': str(STATE / (ticket_id + '.ticket.json')), 'ticket_sha256': installer.digest(raw),
                'reserved_day': day, 'requests_reserved': ticket['request_limit'],
                'response_bytes_reserved': ticket['response_byte_limit'], 'provider_calls': 0,
                'current_day_accounting': engine.budget_summary(engine.STATE, at), 'unattended_available': False}


def import_result(path, ticket_id, commit, *, at=None):
    fixed_time = at is not None
    at = at or engine.now()
    require(re.fullmatch('[a-f0-9]{32}', ticket_id), 'ticket_invalid')
    state_directory()
    path = Path(path).absolute()
    engine.backup.private_dir(path.parent)
    raw = engine.offsite.read_private(path, 262144)
    failure = 'evidence_invalid'
    started = False
    try:
        with engine.exclusion(engine.STATE):
            state = read_state()
            require(state['state'] == 'awaiting_external_audit' and state['ticket_id'] == ticket_id, 'ticket_invalid')
            ticket_raw = engine.offsite.read_private(STATE / (ticket_id + '.ticket.json'), 16384)
            ticket = json.loads(ticket_raw)
            started = True
            # Retain even a rejected/failed result verbatim for diagnosis. Never credentials/raw HTTP.
            engine.backup.write_private(STATE / (ticket_id + '.returned.json'), raw)
            audit = json.loads(raw)
            journal = engine.budget_ledger(engine.STATE / 'budget.json', at)
            reservation_binding(ticket, ticket_raw, journal)
            require(audit.get('status') == 'verified_over_observed_interval', 'audit_failed')
            collector.validate_result(audit, ticket, at)
            require(audit['ticket_sha256'] == installer.digest(ticket_raw), 'ticket_invalid')
            limits, prior = historical_limits()
            require(installer.digest(prior) == ticket['expected_policy_sha256'], 'policy_conflict')
            observed = engine.timestamp(audit['scans'][-1]['completed_at'])
            require(observed > engine.timestamp(limits['observed_at']), 'evidence_invalid')
            directory = allocation.EVIDENCE_ROOT / ('renewal-' + ticket_id)
            engine.backup.private_dir(directory, create=True)
            current_contract = json.loads(engine.offsite.read_private(allocation.CONTRACT, 262144))
            old_directory = Path(current_contract['evidence_directory'])
            old_updated = allocation.artifact(current_contract['operating_evidence'], old_directory)
            candidate = dict(limits, observed_at=observed.isoformat(),
                account_storage_used_bytes_at_observation=audit['account_total_bytes'],
                scope_storage_bytes_at_observation=audit['quillmd_scope_bytes'])
            updated = {'policy_candidate': candidate, 'provider_caps_observation': old_updated['provider_caps_observation'],
                       'caps_are_historical': True, 'administrative_caps_unchanged_assumption': True}
            updated_raw = installer.encoded(updated)
            provenance = {'source': 'operator_imported_portable_collector', 'vps_performed_account_scans': False,
                'semantic_consistency_verified': True, 'source_artifact_sha256': installer.digest(raw),
                'ticket_sha256': installer.digest(ticket_raw), 'original_bytes_preserved': True,
                'local_artifact_hashes': {'account-audit.json': installer.digest(raw),
                                         'operating-evidence.json': installer.digest(updated_raw)}}
            for name, value in (('account-audit.json', raw), ('ticket.json', ticket_raw),
                                ('operating-evidence.json', updated_raw), ('provenance.json', installer.encoded(provenance))):
                engine.backup.write_private(directory / name, value)
            installer.fsync_directory(directory)
            engine.atomic(STATE / 'status.json', dict(state, state='importing', reason_code=None,
                                                    last_attempt_at=at.isoformat()))
        failure = 'publication_failed'
        result = installer.install_pair(directory, commit, execute=True, at=at if fixed_time else None,
                                        expected_previous_sha256=ticket['expected_policy_sha256'])
        with engine.exclusion(engine.STATE):
            state = read_state()
            require(state['state'] == 'importing' and state['ticket_id'] == ticket_id, 'policy_conflict')
            engine.atomic(STATE / 'status.json', dict(state, state='installed', reason_code=None,
                                                    last_attempt_at=at.isoformat()))
            engine.backup.write_private(STATE / (ticket_id + '.installed.json'), installer.encoded(result))
        return result
    except Exception as error:
        reason = getattr(error, 'code', failure)
        if reason not in REASONS:
            reason = failure
        if started:
            with engine.exclusion(engine.STATE):
                state = read_state()
                if state['ticket_id'] == ticket_id:
                    engine.atomic(STATE / 'status.json', dict(state, state='failed', reason_code=reason,
                                                            last_attempt_at=at.isoformat()))
        raise Refusal(reason) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('status')
    issue = commands.add_parser('issue-ticket')
    issue.add_argument('--not-before', required=True)
    issue.add_argument('--valid-until', required=True)
    accept = commands.add_parser('import-result')
    accept.add_argument('--result', required=True)
    accept.add_argument('--ticket-id', required=True)
    for command in (issue, accept):
        command.add_argument('--expected-commit', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'status':
        result = renewal_status()
    else:
        installer.schedule.scope()
        installer.base.reviewed_source(args.expected_commit, mutation=True)
        result = (issue_ticket(args.not_before, args.valid_until, args.expected_commit)
                  if args.action == 'issue-ticket' else import_result(args.result, args.ticket_id, args.expected_commit))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'success': False, 'reason_code': getattr(error, 'code', 'state_invalid'),
                          'policy_not_renewed': True, 'inspect_protected_history': True}))
        raise SystemExit(2)
