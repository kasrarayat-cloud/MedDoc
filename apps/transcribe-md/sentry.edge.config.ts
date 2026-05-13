// ============================================================================
// Sentry — edge runtime init (TranscribeMD) — T-M16.3
// ----------------------------------------------------------------------------
// Edge runtime can't load @meddoc/ai (its barrel re-exports prompt-hash
// which uses node:crypto). The PHI scrubber is short — inlined here
// so the edge config stays edge-safe. Keep the regex patterns in sync
// with packages/ai/src/log.ts.
// ----------------------------------------------------------------------------
// 2026-05-13 audit P1-B — scrubSentryEvent extended to walk
// event.request.data / .url / .query_string / .headers / .cookies and
// event.user. The helper is pure string-ops (no node-crypto), so it's
// edge-safe.
// ============================================================================

import * as Sentry from '@sentry/nextjs';
import { scrubSentryEvent } from '@/lib/sentry-scrub';

const dsn =
  process.env.SENTRY_DSN_TRANSCRIBE_MD?.trim() ||
  process.env.SENTRY_DSN?.trim();

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
  environment:
    process.env.SENTRY_ENVIRONMENT?.trim() || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE?.trim() || undefined,
  tracesSampleRate: 0,
  sendDefaultPii: false,
  beforeSend(event) {
    if (!dsn) return null;
    scrubSentryEvent(event, redactPhi);
    return event;
  },
});
