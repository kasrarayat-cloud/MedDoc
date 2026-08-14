// ============================================================================
// /dev/states — reachable on the CI image, absent from production.
// ----------------------------------------------------------------------------
// ⚠️ A BUILD FLAG, NOT `NODE_ENV`, AND THE DIFFERENCE IS THE WHOLE POINT.
//
// The obvious gate for a dev-only route is `NODE_ENV === 'production'`. It is
// wrong for anything a TEST needs to reach, because the QA stack runs a
// production build. Measured rather than reasoned, on the running stack —
// ⚠️ and HISTORICAL: the route it was measured against, `/dev/rx-warnings`, was
// deleted by owner ruling #109, so this cannot be re-run as written:
//
//   · the QA container reports `NODE_ENV=production`
//   · `/dev/rx-warnings` returned 404 on QA — against a `/login` control
//     returning 200, so the traversal was real
//   · zero E2E specs reference any `/dev/` route
//
// So a NODE_ENV-gated preview route is unreachable by every pack, including
// the Gate C sweep it would exist to serve. It would be a door onto nothing.
//
// A build flag inverts that cleanly: the `:rounds` CI image passes it, so the
// route exists exactly where the sweep runs; production's compose never passes
// it, so it defaults false and the route 404s there. `gate-devstates` asserts
// the production half against the compose file rather than trusting a default,
// because a default is only as good as everyone's memory of it.
//
// Strict equality, like every other flag in this codebase: unset, '1' and
// 'TRUE' are all off.
// ============================================================================

export const DEV_STATES_FLAG = 'NEXT_PUBLIC_DEV_STATES';

export function isDevStates(): boolean {
  return process.env.NEXT_PUBLIC_DEV_STATES === 'true';
}
