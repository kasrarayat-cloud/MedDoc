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
export const APP_SIGNUP_URL = `${APP_URL}/signup`;
