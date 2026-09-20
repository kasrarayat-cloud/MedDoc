#!/usr/bin/env python3
"""Install or renew finite desktop account evidence without changing provider caps or the budget journal."""
import argparse
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets

try:
    from . import automatic_offsite as engine, offsite_allocation as allocation, install_offsite_schedule as schedule
except ImportError:
    import automatic_offsite as engine
    import offsite_allocation as allocation
    import install_offsite_schedule as schedule

base = schedule.base


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def candidate_pair(directory):
    directory = Path(directory).absolute()
    base.require(directory.parent == allocation.EVIDENCE_ROOT and directory.resolve() == directory,
                 'Use an immediate protected account-evidence directory without symlinks.')
    engine.backup.private_dir(directory)
    raw = {name: engine.offsite.read_private(directory / name, 262144)
           for name in ('account-audit.json', 'operating-evidence.json', 'provenance.json')}
    audit, updated = json.loads(raw['account-audit.json']), json.loads(raw['operating-evidence.json'])
    limits = dict(updated['policy_candidate'])
    base.require(set(limits) == engine.POLICY_FIELDS, 'Expected the existing 17-field operating policy.')
    observed = engine.timestamp(audit['scans'][-1]['completed_at'])
    base.require(engine.timestamp(limits['observed_at']) == observed
                 and limits['account_storage_used_bytes_at_observation'] == audit['account_total_bytes']
                 and limits['scope_storage_bytes_at_observation'] == audit['quillmd_scope_bytes'],
                 'Candidate and original account observation disagree.')
    limits.update(approved=True, approval_reference=schedule.DECLARATION,
                  observed_at=observed.isoformat(), valid_until=(observed + timedelta(hours=24)).isoformat(),
                  exclusive_scope_allocation_confirmed=True, exclusive_daily_budgets_confirmed=True,
                  scope_storage_ceiling_bytes=1_000_000_000, daily_download_budget_bytes=100_000_000,
                  daily_request_budget=500, max_run_seconds=900, max_local_age_hours=30)
    non_scope = audit['account_total_bytes'] - audit['quillmd_scope_bytes']
    contract = {'version': 1, 'status': 'active', 'policy_sha256': digest(encoded(limits)),
                'observed_at': limits['observed_at'], 'valid_until': limits['valid_until'],
                'evidence_directory': str(directory),
                'windows_source_sha256': updated['account_audit']['source_sha256'],
                'control_sources': {relative: digest((allocation.ROOT / relative).read_bytes())
                                    for relative in allocation.SOURCES},
                'known_consumers': list(allocation.CONSUMERS),
                'administrative_constraints': list(allocation.CONSTRAINTS),
                'non_scope_observed_bytes': non_scope,
                'account_reserved_bound_bytes': non_scope + limits['scope_storage_ceiling_bytes'],
                'renewal_requires_desktop': True, 'key_inventory_complete': False, 'future_budget_guarantee': False}
    for field, name in (('audit', 'account-audit.json'), ('operating_evidence', 'operating-evidence.json'),
                        ('provenance', 'provenance.json')):
        contract[field] = {'name': name, 'local_sha256': digest(raw[name])}
    return limits, contract


def install_pair(directory, commit, *, execute=False, at=None):
    """Called after reviewed_source; one locked publication, with a fail-closed marker on partial failure."""
    fixed_time = at is not None  # Deterministic isolated fixtures; CLI always rechecks the current clock.
    at = at or engine.now()
    with engine.exclusion(engine.STATE):
        limits, contract = candidate_pair(directory)
        base.require(engine.timestamp(limits['observed_at']) <= at < engine.timestamp(limits['valid_until']),
                     'Original account observation has expired; its timestamp cannot be refreshed locally.')
        result = {'version': 1, 'commit': commit, 'provider_calls': 0, 'application_restart': False,
                  'success': False, 'execute': execute, 'observed_at': limits['observed_at'],
                  'valid_until': limits['valid_until'], 'account_reserved_bound_bytes': contract['account_reserved_bound_bytes'],
                  'renewal_requires_desktop': True, 'policy_sha256': digest(encoded(limits)),
                  'contract_sha256': digest(encoded(contract))}
        if not execute:
            return dict(result, plan_prepared=True, fixed_files_changed=False,
                        candidate_validation='performed before publication by --execute')
        engine.backup.private_dir(base.EVIDENCE)
        parent = engine.offsite.CONFIG_PARENT
        engine.backup.private_dir(parent)
        marker = parent / 'offsite-policy-installing.json'
        base.require(not marker.exists() and not marker.is_symlink(),
                     'Unfinished policy installation requires inspection; retain its failure evidence.')
        name = 'policy-' + at.strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4)
        candidate, companion = parent / (name + '.json'), parent / (name + '-allocation.json')
        ledger_before = engine.offsite.read_private(allocation.LEDGER, 4 * 1024 * 1024)
        previous = {}
        for label, path in (('policy', engine.POLICY), ('allocation', allocation.CONTRACT)):
            if path.exists() or path.is_symlink():
                prior = engine.offsite.read_private(path, 262144)
                engine.backup.write_private(base.EVIDENCE / (name + '-previous-' + label + '.json'), prior)
                previous[label] = digest(prior)
        engine.backup.write_private(base.EVIDENCE / (name + '-intent.json'), encoded({
            **result, 'policy': limits, 'allocation': contract, 'previous': previous,
            'ledger_sha256_before': digest(ledger_before)}))
        stage = 'candidate_validation'
        try:
            engine.backup.write_private(candidate, encoded(limits))
            engine.backup.write_private(companion, encoded(contract))
            engine.policy(candidate, at)
            allocation.validate(limits, candidate, at, contract_path=companion)
            engine.backup.write_private(marker, encoded({'attempt': name, 'commit': commit}))
            fsync_directory(parent)
            stage = 'publication'
            os.replace(companion, allocation.CONTRACT)
            os.replace(candidate, engine.POLICY)
            fsync_directory(parent)
            base.require(engine.offsite.read_private(engine.POLICY, 16384) == encoded(limits)
                         and engine.offsite.read_private(allocation.CONTRACT, 262144) == encoded(contract),
                         'Published policy bytes differ from the validated candidates.')
            allocation.validate(limits, engine.POLICY, at, contract_path=allocation.CONTRACT)
            base.require(engine.offsite.read_private(allocation.LEDGER, 4 * 1024 * 1024) == ledger_before,
                         'Policy installation cannot reset or change the shared journal.')
            marker.unlink()
            fsync_directory(parent)
            stage = 'installed_validation'
            engine.policy(engine.POLICY, at if fixed_time else None)
            result.update(success=True, previous=previous, fixed_files_changed=True,
                          shared_journal_unchanged=True, ledger_sha256=digest(ledger_before))
            return result
        except Exception:
            result.update(failed_stage=stage, fixed_files_may_have_changed=stage != 'candidate_validation',
                          failure='Policy installation failed; inspect protected intent/result and any publication marker.')
            raise
        finally:
            result['finished_at'] = engine.now().isoformat()
            cleanup_failed = False
            for path in (candidate, companion):
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    cleanup_failed = True
            try:
                fsync_directory(parent)
            except OSError:
                cleanup_failed = True
            if cleanup_failed:
                result.update(success=False, cleanup_failed=True)
                result.setdefault('failed_stage', 'candidate_cleanup')
            engine.backup.write_private(base.EVIDENCE / (name + '-result.json'), encoded(result))
            base.require(not cleanup_failed, 'Policy candidate cleanup failed; inspect retained evidence.')


def main():
    schedule.scope()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--evidence-directory', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    base.require(os.getuid() == pwd.getpwnam('claude').pw_uid, 'Use the authorized project operator.')
    os.umask(0o077)
    base.reviewed_source(args.expected_commit, mutation=args.execute)
    result = install_pair(args.evidence_directory, args.expected_commit, execute=args.execute)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Offsite policy installation refused. Preserve protected intent/result evidence; no provider details emitted.')
