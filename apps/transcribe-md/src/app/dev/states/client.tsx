'use client';

// ============================================================================
// The client island for /dev/states.
// ----------------------------------------------------------------------------
// `ErrorFallback` is a client component taking an `error` and a `reset`, so the
// deterministic way to render BOTH of its branches is to hand it the error that
// produces each — not to throw and hope the boundary catches the right shape.
//
// ⚠️ THE STALE FIXTURE IS BUILT FROM THE DETECTOR'S OWN CONTRACT, not from a
// string someone remembered. `isStaleDeploymentError` matches 'unrecognizedaction',
// 'older or newer deployment', or 'server action' + 'was not found'/'failed to
// find'. If that predicate changes, this fixture silently stops producing the
// stale branch while the page still labels it as one — so `gate-devstates`
// asserts the predicate still sorts both fixtures the way this page claims.
//
// ⚠️ `preview` IS PASSED. Without it every visit to this route POSTs a
// synthetic error to `/api/client-errors`, indistinguishable to ops from a real
// one and arriving from a URL that looks like a real page.
// ============================================================================

import { ErrorFallback } from '@/components/error-fallback';
import { isStaleDeploymentError } from '@/lib/stale-deployment';

/** The two errors that drive the boundary's two branches. Exported so the
 *  guard can assert the detector still sorts them as this page claims. */
export const DEV_PLAIN_ERROR = Object.assign(
  new Error('Something unexpected happened while loading this visit.'),
  { digest: 'devplain0' },
);
export const DEV_STALE_ERROR = Object.assign(
  new Error(
    'Failed to find Server Action "abc123". This browser tab was loaded before a deployment.',
  ),
  { digest: 'devstale0' },
);

export function DevErrorState({ stale }: { stale: boolean }) {
  const error = stale ? DEV_STALE_ERROR : DEV_PLAIN_ERROR;
  return (
    <div data-testid={stale ? 'dev-error-stale' : 'dev-error-plain'}>
      <p
        data-testid="dev-error-classification"
        style={{ fontFamily: 'var(--font-mono)', fontSize: 11, opacity: 0.6, padding: '8px 16px' }}
      >
        isStaleDeploymentError(fixture) = {String(isStaleDeploymentError(error))}
      </p>
      <ErrorFallback error={error} reset={() => undefined} scope="root" preview />
    </div>
  );
}
