// ============================================================================
// apps/transcribe-md — shared URL constants
// ----------------------------------------------------------------------------
// Centralises URLs that the marketing site + the app both need to agree on
// so a domain cutover is a one-line change per package. Also re-exported
// from apps/marketing so both surfaces stay in sync.
// ============================================================================

/** Public URL of the TranscribeMD app (where doctors sign up + work).
 *  Defaults to the VPS public IP on :9020 — updates once DNS + TLS land. */
export const APP_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL ??
  'http://5.231.107.93:9020';

/** Public URL of the marketing site. */
export const MARKETING_URL =
  process.env.NEXT_PUBLIC_MARKETING_URL ?? 'http://5.231.107.93:9010';
