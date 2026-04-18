// ============================================================================
// apps/transcribe-md — device fingerprint helpers
// ----------------------------------------------------------------------------
// The shared @meddoc/auth package already computes + stores a fingerprint
// on login via the jwt() callback. This module exposes helpers for the
// /settings page to parse a stored UserSession row back into a
// human-readable "browser/OS" string for display.
// ============================================================================

export interface ParsedUserAgent {
  browser: string;
  os: string;
}

/** Extremely lightweight UA parser. Covers the common cases we actually see
 *  and stays dependency-free; a full solution (ua-parser-js etc.) is worth
 *  pulling in when we need OS/version fidelity for support triage. */
export function parseUserAgent(ua: string | null | undefined): ParsedUserAgent {
  if (!ua) return { browser: 'Unknown', os: 'Unknown' };
  const s = ua.toLowerCase();

  let browser = 'Unknown';
  if (s.includes('edg/')) browser = 'Edge';
  else if (s.includes('chrome/') && !s.includes('chromium')) browser = 'Chrome';
  else if (s.includes('firefox/')) browser = 'Firefox';
  else if (s.includes('safari/') && !s.includes('chrome')) browser = 'Safari';
  else if (s.includes('opr/') || s.includes('opera')) browser = 'Opera';

  let os = 'Unknown';
  if (s.includes('windows')) os = 'Windows';
  else if (s.includes('mac os x') || s.includes('macintosh')) os = 'macOS';
  else if (s.includes('android')) os = 'Android';
  else if (s.includes('iphone') || s.includes('ipad')) os = 'iOS';
  else if (s.includes('linux')) os = 'Linux';

  return { browser, os };
}

/** Lossy single-line summary for display: "Chrome on macOS". */
export function describeUserAgent(ua: string | null | undefined): string {
  const { browser, os } = parseUserAgent(ua);
  return `${browser} on ${os}`;
}

/** Rough location label from an IP. We don't ship geoip-lite in this
 *  milestone — it adds ~30MB to the container and is overkill for a
 *  shell. Instead we display the IP itself, with a note. T-M2.5 can
 *  add a real IP→location lookup. */
export function describeIpLocation(ip: string | null | undefined): string {
  if (!ip) return 'Unknown location';
  return `${ip} (location lookup coming in T-M2.5)`;
}
