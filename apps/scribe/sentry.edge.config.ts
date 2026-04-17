// ============================================================================
// Sentry — edge runtime init (Scribe) — M7
// ----------------------------------------------------------------------------
// Edge-safe: inline PHI scrubber (the @meddoc/ai barrel drags in
// node:crypto via prompt-hash, which edge runtime can't load).
// ============================================================================

import * as Sentry from '@sentry/nextjs';

const dsn = process.env.SENTRY_DSN_SCRIBE?.trim() || process.env.SENTRY_DSN?.trim();

const EMAIL_RE = /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g;
const PHONE_RE = /\(?\+?\d[\d \-()]{8,}\d/g;
const SSN_RE = /\b\d{3}-?\d{2}-?\d{4}\b/g;
const MAX_WORDS_BEFORE_REDACT = 20;

function redactPhi(input: unknown): string {
  if (input === null || input === undefined) return String(input);
  let s = typeof input === 'string' ? input : JSON.stringify(input);
  s = s.replace(EMAIL_RE, '[EMAIL]');
  s = s.replace(SSN_RE, '[SSN]');
  s = s.replace(PHONE_RE, '[PHONE]');
  const words = s.trim().split(/\s+/).filter(Boolean);
  if (words.length > MAX_WORDS_BEFORE_REDACT) {
    return `[REDACTED:${words.length}w]`;
  }
  return s;
}

Sentry.init({
  dsn: dsn || undefined,
  environment: process.env.SENTRY_ENVIRONMENT?.trim() || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE?.trim() || undefined,
  tracesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    if (typeof event.message === 'string') {
      event.message = redactPhi(event.message);
    }
    return event;
  },
});
