// ============================================================================
// apps/marketing — shared URL constants
// ----------------------------------------------------------------------------
// Every "Start free trial" CTA on the marketing site links to
// `${APP_URL}/signup` via APP_SIGNUP_URL below. When DNS + HTTPS land
// and we cut over to a real domain, this becomes a one-line change.
// ============================================================================

/** Where doctors actually sign up + use TranscribeMD. IP-based default
 *  is the author-preview public URL (T-M2); override via
 *  NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL at build time for prod. */
export const APP_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL ??
  'http://5.231.107.93:9020';

/** Convenience — the most common CTA destination. */
/**
 * Where every marketing CTA points.
 *
 * INVITE-ONLY PILOT (2026-07-28): this is the WAITLIST, not signup. Open
 * registration bought 195 accounts of which 172 never logged in, so the app's
 * /signup now requires an invite code and a cold CTA landing there would just
 * fail. The waitlist creates no account — see actions/waitlist.ts.
 *
 * `APP_SIGNUP_URL` is kept as a deprecated alias so a stale import cannot
 * silently point a button back at a door that is closed.
 */
export const APP_WAITLIST_URL = `${APP_URL}/waitlist`;

/** @deprecated Use APP_WAITLIST_URL. Retained so any missed import still lands
 *  on the waitlist rather than on the invite-gated signup form. */
export const APP_SIGNUP_URL = APP_WAITLIST_URL;
