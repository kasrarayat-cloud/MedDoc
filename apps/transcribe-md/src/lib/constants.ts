// ============================================================================
// apps/transcribe-md — shared URL constants
// ----------------------------------------------------------------------------
// Centralises URLs that the marketing site + the app both need to agree on
// so a domain cutover is a one-line change per package. Also re-exported
// from apps/marketing so both surfaces stay in sync.
// ============================================================================

/** Public URL of the TranscribeMD physician app. Production startup also
 * verifies this build-inlined value against the reviewed HTTPS origin. */
export const APP_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL ?? "https://app.quillmd.com";

/** Public URL of the marketing site. */
export const MARKETING_URL =
  process.env.NEXT_PUBLIC_MARKETING_URL ?? "https://quillmd.com";
