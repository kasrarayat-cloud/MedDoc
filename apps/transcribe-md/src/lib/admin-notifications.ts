// ============================================================================
// Admin failure-alert email (commit 3 of fix/voice-retry-robustness).
// ----------------------------------------------------------------------------
// Worker calls notifyAdminOnFailure() every time it persists a visit
// to FAILED — i.e., the user is now staring at the red banner. The
// recipient is whoever's in ADMIN_ALERT_EMAIL (default: kasra), which
// in pilot phase is the human who needs to look at it and decide
// whether to hand-fix or ping the doctor.
//
// Three guards keep this from becoming a notification firehose:
//
//   1. Kill switch — ADMIN_ALERT_ENABLED=false skips the send
//      entirely (used in tests / staging).
//
//   2. Per-user-per-day throttle — at most one alert per (userId,
//      UTC calendar day) via a Redis SET with NX (only-if-absent)
//      and a 25-hour TTL. A wedged pipeline that fails ten times in
//      a row for the same user emails once.
//
//   3. Best-effort delivery — every failure path inside this module
//      is caught and logged. Notify failures NEVER throw back into
//      the worker's catch block; otherwise a misconfigured Resend
//      key would mask the underlying pipeline error in Sentry.
//
// PHI posture: the email body deliberately includes only IDs +
// scrubbed error message (we ask for a redactPhi-cleaned `error`
// string at the call site). The recipient's user email is the
// caller's domain only — the local-part is replaced with `<doctor>`
// so a leaked / forwarded alert doesn't expose patient-association.
// ============================================================================

import { Resend } from 'resend';
import { escapeHtml } from './html-escape';

import { getSharedRedisConnection } from './queue';
import { log } from './log';
import { redactPhi } from '@meddoc/ai';

const DEFAULT_FROM = 'QuillMD Alerts <noreply@quillmd.com>';
const DEFAULT_TO = 'kasra.rayat@gmail.com';
const THROTTLE_TTL_SECONDS = 25 * 60 * 60; // 25h covers UTC day rollover

export interface AdminAlertInput {
  visitId: string;
  userId: string;
  userEmail: string | null;
  practiceId: string | null;
  layer: string;
  category: string;
  /** Already-scrubbed (redactPhi'd) error message from the worker. */
  scrubbedError: string;
  /** Optional — audio length if known. Helps triage "did Deepgram
   *  choke on a long file vs a short one?". */
  audioDurationSec?: number | null;
}

export interface AdminAlertResult {
  ok: boolean;
  reason?: 'disabled' | 'throttled' | 'send_failed' | 'misconfigured';
  /** Resend message id when successfully sent. */
  messageId?: string;
}

function isEnabled(): boolean {
  // Default ON. Set ADMIN_ALERT_ENABLED=false to mute (tests, staging,
  // an outage where the alerts themselves are misbehaving).
  const raw = process.env.ADMIN_ALERT_ENABLED?.trim().toLowerCase();
  return raw !== 'false' && raw !== '0' && raw !== 'no';
}

function recipientEmail(): string {
  return process.env.ADMIN_ALERT_EMAIL?.trim() || DEFAULT_TO;
}

function senderFrom(): string {
  return process.env.RESEND_FROM?.trim() || DEFAULT_FROM;
}

/** Returns the local part of an email if obvious; falls back to a
 *  placeholder. Used to avoid splatting a doctor's full address into
 *  the alert body — the alert reader needs the domain (multi-tenant
 *  triage) but not the local-part. */
function obscureEmail(email: string | null): string {
  if (!email) return '<unknown>';
  const at = email.lastIndexOf('@');
  if (at < 1) return '<unknown>';
  return `<doctor>${email.slice(at)}`;
}

function todayUtcKey(): string {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

/** Per-user-per-day single-shot guard. Uses Redis SET NX to make the
 *  check + reservation atomic — a wedged pipeline retrying in
 *  parallel can't race two emails out. Any Redis error short-circuits
 *  to "go ahead and send" rather than dropping the alert silently. */
async function tryReserveSlot(userId: string): Promise<boolean> {
  const key = `admin-notify:${userId}:${todayUtcKey()}`;
  try {
    const redis = getSharedRedisConnection();
    const result = await redis.set(key, '1', 'EX', THROTTLE_TTL_SECONDS, 'NX');
    return result === 'OK';
  } catch (err) {
    log.warn(
      'admin-notifications',
      'redis throttle check failed — sending anyway',
      { userId, error: redactPhi(err instanceof Error ? err.message : err) }
    );
    return true;
  }
}

function buildBody(input: AdminAlertInput): { subject: string; html: string; text: string } {
  const subject = `[QuillMD] Visit ${input.visitId} failed after retries — ${input.layer}`;
  const lines = [
    `Layer:           ${input.layer}`,
    `Category:        ${input.category}`,
    `Visit ID:        ${input.visitId}`,
    `User ID:         ${input.userId}`,
    `User email:      ${obscureEmail(input.userEmail)}`,
    `Practice ID:     ${input.practiceId ?? '<unknown>'}`,
    `Audio duration:  ${
      input.audioDurationSec != null
        ? `${Math.round(input.audioDurationSec)}s`
        : '<unknown>'
    }`,
    '',
    'Scrubbed error message:',
    input.scrubbedError || '<empty>',
  ];
  const text = lines.join('\n');
  const html = `<pre style="font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap;">${escapeHtml(
    text
  )}</pre>`;
  return { subject, html, text };
}


let clientSingleton: Resend | null = null;
function getResend(): Resend | null {
  if (clientSingleton) return clientSingleton;
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) return null;
  clientSingleton = new Resend(apiKey);
  return clientSingleton;
}

/** Fire-and-forget admin alert. Never throws — every failure logs
 *  and returns a structured result so callers can opt to surface it
 *  in their own logs but don't have to wrap a try/catch. */
export async function notifyAdminOnFailure(
  input: AdminAlertInput
): Promise<AdminAlertResult> {
  if (!isEnabled()) {
    log.info('admin-notifications', 'alerts disabled, skipping', {
      visitId: input.visitId,
    });
    return { ok: false, reason: 'disabled' };
  }

  const reserved = await tryReserveSlot(input.userId);
  if (!reserved) {
    log.info('admin-notifications', 'throttled (already alerted today)', {
      userId: input.userId,
      visitId: input.visitId,
    });
    return { ok: false, reason: 'throttled' };
  }

  const client = getResend();
  if (!client) {
    log.warn('admin-notifications', 'RESEND_API_KEY unset — alert not sent', {
      visitId: input.visitId,
    });
    return { ok: false, reason: 'misconfigured' };
  }

  const body = buildBody(input);
  try {
    const result = await client.emails.send({
      from: senderFrom(),
      to: recipientEmail(),
      subject: body.subject,
      html: body.html,
      text: body.text,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const messageId = ((result as any)?.data?.id as string | undefined) ?? undefined;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sendErr = (result as any)?.error;
    if (sendErr) {
      log.error('admin-notifications', 'resend returned error', {
        visitId: input.visitId,
        error: redactPhi(
          typeof sendErr === 'string' ? sendErr : sendErr?.message ?? '<unknown>'
        ),
      });
      return { ok: false, reason: 'send_failed' };
    }
    log.info('admin-notifications', 'alert sent', {
      visitId: input.visitId,
      messageId,
    });
    return { ok: true, messageId };
  } catch (err) {
    log.error('admin-notifications', 'send threw', {
      visitId: input.visitId,
      error: redactPhi(err instanceof Error ? err.message : err),
    });
    return { ok: false, reason: 'send_failed' };
  }
}
