// ============================================================================
// Next.js "deployment skew" detection.
// ----------------------------------------------------------------------------
// When a tab was loaded BEFORE a deploy, its client bundle references server-
// action IDs (content hashes) that the freshly-built server no longer has. The
// next action POST then fails with UnrecognizedActionError / "Failed to find
// Server Action … This request might be from an older or newer deployment."
//
// This is transient + self-healing: a FULL page reload fetches the new bundle
// with current action IDs. A React error-boundary reset() or re-render does NOT
// help (it re-mounts the same stale bundle). So callers use this to show a
// "reload to continue" prompt instead of a generic crash, and to preserve the
// user's in-progress input rather than dumping them to the error page.
// ============================================================================

/** True if `error` is the Next.js stale-deployment / unknown-server-action
 *  error. Defensive against shape (digest-only prod errors, missing fields). */
export function isStaleDeploymentError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const e = error as { name?: unknown; message?: unknown; digest?: unknown };
  const hay = [e.name, e.message, e.digest]
    .filter((v): v is string => typeof v === 'string')
    .join(' ')
    .toLowerCase();
  if (hay.includes('unrecognizedaction')) return true;
  if (hay.includes('older or newer deployment')) return true;
  // "Server Action <hash> was not found on the server" / "Failed to find Server
  // Action …". Anchor on the 'server action' context so a generic 404-style
  // "<x> was not found on the server" can't be mis-routed to a reload prompt.
  return (
    hay.includes('server action') &&
    (hay.includes('was not found') || hay.includes('failed to find'))
  );
}
