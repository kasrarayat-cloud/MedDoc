// ============================================================================
// Sentry event scrubber — extended PHI-hygiene posture (2026-05-13 audit P1-B)
// ----------------------------------------------------------------------------
// The original sentry.*.config.ts files scrubbed event.message,
// event.extra, and event.breadcrumbs[].message via redactPhi. The
// Sentry Next.js integration also auto-attaches:
//
//   event.request.data         — POST body (object or string)
//   event.request.query_string — URL query (string or [k,v][])
//   event.request.url          — full URL incl. query
//   event.request.cookies      — cookies (may carry session info)
//   event.user.email/username  — user identifier
//   event.contexts             — arbitrary structured context
//
// Any of these can quote PHI: a failed POST /api/visits/[id]/text
// puts the dictated text in event.request.data; the /api/patients?
// search=Jane URL puts a patient name in event.request.url + .query_string.
// This helper extends the scrubbing to all of those fields.
//
// The function takes a redactPhi implementation so the edge runtime
// can inject its inlined copy (the edge config can't import
// @meddoc/ai, which transitively uses node:crypto).
// ============================================================================

type ScrubFn = (input: unknown) => string;

/** Header names dropped outright from event.request.headers. All
 *  lowercase; the iteration normalizes the incoming key. Two groups:
 *  credentials (authorization, cookie, csrf, api-key, STS) and
 *  client-IP identifiers (HIPAA §164.514(b) — IPs can re-identify). */
const HEADER_DROP_LIST = new Set([
  'authorization',
  'proxy-authorization',
  'cookie',
  'set-cookie',
  'referer',
  'x-csrf-token',
  'x-api-key',
  'x-amz-security-token',
  'x-forwarded-for',
  'x-real-ip',
  'forwarded',
  'cf-connecting-ip',
  'true-client-ip',
]);

/** In-place rewrite of `event` so every known PHI-bearing surface
 *  passes through `redactPhi`. Drops the user.email / user.ip_address
 *  PII fields entirely; redacts everything else. Safe to call before
 *  Sentry.send. */
export function scrubSentryEvent(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  event: any,
  redactPhi: ScrubFn,
): void {
  // event.message
  if (typeof event.message === 'string') {
    event.message = redactPhi(event.message);
  }

  // event.extra — caller-attached structured context
  if (event.extra && typeof event.extra === 'object') {
    const extra = event.extra as Record<string, unknown>;
    for (const k of Object.keys(extra)) {
      const v = extra[k];
      if (typeof v === 'string') extra[k] = redactPhi(v);
    }
  }

  // event.tags — short string labels; pass through redactPhi as
  // defense against a tagger embedding a name or email.
  if (event.tags && typeof event.tags === 'object') {
    const tags = event.tags as Record<string, unknown>;
    for (const k of Object.keys(tags)) {
      const v = tags[k];
      if (typeof v === 'string') tags[k] = redactPhi(v);
    }
  }

  // event.breadcrumbs[*].message
  if (Array.isArray(event.breadcrumbs)) {
    for (const crumb of event.breadcrumbs) {
      if (crumb && typeof crumb.message === 'string') {
        crumb.message = redactPhi(crumb.message);
      }
      if (crumb && crumb.data && typeof crumb.data === 'object') {
        const d = crumb.data as Record<string, unknown>;
        for (const k of Object.keys(d)) {
          const v = d[k];
          if (typeof v === 'string') d[k] = redactPhi(v);
        }
      }
    }
  }

  // event.request — auto-attached by the Sentry Next.js integration.
  // Walk every PHI-bearing field.
  if (event.request && typeof event.request === 'object') {
    const req = event.request as Record<string, unknown>;

    // URL: strip the query string entirely. The path is enough for
    // operational triage; query strings on /api/patients?search=...
    // and similar routes leak the patient's name.
    if (typeof req.url === 'string') {
      const qIdx = req.url.indexOf('?');
      req.url = qIdx >= 0 ? req.url.slice(0, qIdx) : req.url;
    }

    // query_string: drop entirely (Sentry accepts string OR [k,v][];
    // either is unsafe).
    if ('query_string' in req) {
      delete req.query_string;
    }

    // data: POST body. Stringify-then-redact captures both string
    // bodies and object bodies through the same scrubber.
    if (req.data !== undefined && req.data !== null) {
      const asStr =
        typeof req.data === 'string' ? req.data : JSON.stringify(req.data);
      req.data = redactPhi(asStr);
    }

    // headers: drop the credential + IP family outright; redact the
    // rest. The IP headers are §164.514(b)-identifying and redactPhi
    // doesn't pattern-match IPv4/v6 today — explicit drop is safer
    // than relying on the regex catching them. CSRF / API-key /
    // STS-token headers are credentials and have no place in error
    // reports.
    if (req.headers && typeof req.headers === 'object') {
      const h = req.headers as Record<string, unknown>;
      for (const k of Object.keys(h)) {
        const lower = k.toLowerCase();
        if (HEADER_DROP_LIST.has(lower)) {
          delete h[k];
        } else if (typeof h[k] === 'string') {
          h[k] = redactPhi(h[k] as string);
        }
      }
    }

    // cookies: drop entirely — session tokens never belong in an
    // error report.
    if ('cookies' in req) {
      delete req.cookies;
    }
  }

  // event.user — drop email + ip_address + username; keep id (opaque
  // cuid, useful for correlation). Guard against a future caller
  // passing email/MRN as id by accident: only accept short string ids.
  if (event.user && typeof event.user === 'object') {
    const user = event.user as Record<string, unknown>;
    delete user.email;
    delete user.ip_address;
    delete user.username;
    if (typeof user.id !== 'string' || user.id.length > 64) {
      delete user.id;
    }
  }

  // event.contexts — walk one level deep, scrub strings.
  if (event.contexts && typeof event.contexts === 'object') {
    const contexts = event.contexts as Record<string, unknown>;
    for (const ctxKey of Object.keys(contexts)) {
      const ctx = contexts[ctxKey];
      if (ctx && typeof ctx === 'object') {
        const ctxRec = ctx as Record<string, unknown>;
        for (const k of Object.keys(ctxRec)) {
          const v = ctxRec[k];
          if (typeof v === 'string') ctxRec[k] = redactPhi(v);
        }
      }
    }
  }
}
