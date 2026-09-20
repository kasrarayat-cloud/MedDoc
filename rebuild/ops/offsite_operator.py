#!/usr/bin/env python3
"""Budgeted scoped metadata checks and explicit accounting for external operator work."""
import argparse
import json

try:
    from . import automatic_offsite as engine
except ImportError:
    import automatic_offsite as engine


def inventory():
    """Return only scope facts: this key cannot measure the entire account."""
    with engine.live_session() as transport:
        rows = transport.inventory()
        uploaded = [row for row in rows if row['action'] == 'upload']
        result = {'complete': True, 'source': 'VPS restricted runtime Native API',
                  'scope': 'one approved bucket and QuillMD prefix; not account-wide',
                  'observed_at': engine.now().isoformat(),
                  'retained_versions': len(uploaded),
                  'retained_version_bytes': sum(row['contentLength'] for row in uploaded),
                  'retained_names': len({row['fileName'] for row in uploaded}),
                  'hide_markers': sum(row['action'] == 'hide' for row in rows),
                  'unfinished_uploads': 0,
                  'shared_accounting': True, 'provider_mutations': 0}
    # Session cleanup has to succeed before a complete report can escape.
    return result


def reserve_external(requests, download_bytes, reference):
    """Debit the shared ledger without reading credentials or contacting a provider."""
    with engine.exclusion(engine.STATE):
        limits = engine.policy(engine.POLICY)
        budget = engine.Budget(engine.STATE, limits)
        record = budget.reserve_external(requests, download_bytes, reference)
        return {'complete': True, 'provider_calls': 0, 'reservation': record,
                'shared_budget': engine.budget_summary(engine.STATE)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('inventory', help='Budgeted scoped versions/unfinished-upload check; no object contents.')
    reserve = commands.add_parser('reserve-external', help='Record or pre-reserve external administrative consumption.')
    reserve.add_argument('--requests', required=True, type=int)
    reserve.add_argument('--download-bytes', required=True, type=int)
    reserve.add_argument('--reference', required=True,
                         help='Unique nonsecret evidence/reference name; never a credential or provider response.')
    args = parser.parse_args()
    result = inventory() if args.action == 'inventory' else reserve_external(
        args.requests, args.download_bytes, args.reference)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except engine.Refusal as error:
        print(json.dumps({'complete': False, 'reason_code': error.code}))
        raise SystemExit(2)
    except Exception:
        raise SystemExit('Offsite operator action refused. Preserve protected evidence; provider details withheld.')
