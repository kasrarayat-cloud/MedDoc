// ============================================================================
// Email sender — Resend (T-M7)
// ----------------------------------------------------------------------------
// Doctor-only delivery path. Sends the signed visit PDF to the clinician
// themselves (or another address they type in the Sign & Send modal).
//
// This is NOT for patient comms. HIPAA-compliant patient email is a
// bigger scope (encrypted transport, consent on file, etc.) and isn't
// in T-M7.
// ============================================================================

import { Resend } from 'resend';
import { escapeHtml } from './html-escape';

// Phase 6Z (PHASE-6Z-07): Resend wraps were never wired to logApiUsage,
// so api_usage_events had no `provider='resend'` rows and the /admin/usage
// breakdown silently undercounted total spend. Wired below at the two
// success-path return points (sendOne + sendVisitPdfEmail).
import { logApiUsage, buildResendUsage } from '@meddoc/ai';

/** Thrown when Resend rejects the send because the deployment isn't
 *  set up correctly (domain not verified, API key revoked, etc.) —
 *  i.e., a CONFIG error the ops team needs to fix, not a per-message
 *  transient error. Callers can distinguish this from "delivery
 *  failed" and surface it more prominently. */
export class EmailNotConfiguredError extends Error {
  readonly code = 'EMAIL_NOT_CONFIGURED' as const;
  constructor(message: string) {
    super(message);
    this.name = 'EmailNotConfiguredError';
  }
}

let clientSingleton: Resend | null = null;

function getClient(): Resend {
  if (clientSingleton) return clientSingleton;
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    throw new EmailNotConfiguredError(
      'RESEND_API_KEY is not set — email delivery is disabled on this deployment.'
    );
  }
  clientSingleton = new Resend(apiKey);
  return clientSingleton;
}

/** From-address defaults to noreply@quillmd.com — that domain is
 *  verified (DKIM + SPF + DMARC + MX) in the Resend account attached
 *  to RESEND_API_KEY as of T-M19.3 (2026-04-21). Override with
 *  RESEND_FROM="Name <addr@verified-domain.tld>" in .env if you need
 *  a different sender (e.g. support@quillmd.com for support mail).
 *  The override wins; this constant is just the fallback for a
 *  deploy that forgot to set RESEND_FROM. */
const DEFAULT_FROM = 'QuillMD <noreply@quillmd.com>';

export interface SendVisitPdfEmailArgs {
  toEmail: string;
  visitId: string;
  /** Raw PDF bytes from pdf-generator. */
  pdfBuffer: Buffer;
  /** Display name for greeting + attachment filename. */
  doctorName: string | null;
  /** Optional patient name — shown in the subject line when present. */
  patientName: string | null;
  /** ISO YYYY-MM-DD of the visit — used in attachment filename. */
  visitDate: string;
}

export interface SendVisitPdfEmailResult {
  id: string | null;
  toEmail: string;
}

export async function sendVisitPdfEmail(
  args: SendVisitPdfEmailArgs
): Promise<SendVisitPdfEmailResult> {
  const client = getClient();
  const from = process.env.RESEND_FROM?.trim() || DEFAULT_FROM;

  const subjectTail = args.patientName?.trim()
    ? ` — ${args.patientName.trim()}`
    : ' — signed visit';
  const subject = `Your QuillMD visit note${subjectTail}`;
  const greeting = args.doctorName?.trim()
    ? `Hi ${args.doctorName.trim()},`
    : 'Hi,';

  const html = [
    `<p>${greeting}</p>`,
    `<p>Your signed visit note is attached as a PDF.</p>`,
    `<p style="color:#666;font-size:13px;">This email is for your records. Do not forward to patients — QuillMD does not handle patient-facing delivery yet. For patient hand-off, download the PDF and share through your usual secure channel.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · signed ${args.visitDate}</p>`,
  ].join('\n');

  const text = [
    greeting,
    '',
    'Your signed visit note is attached as a PDF.',
    '',
    'This email is for your records. Do not forward to patients — QuillMD does not handle patient-facing delivery yet. For patient hand-off, download the PDF and share through your usual secure channel.',
    '',
    `—`,
    `QuillMD · signed ${args.visitDate}`,
  ].join('\n');

  const filename = `visit-${args.visitId}-${args.visitDate}.pdf`;

  const result = await client.emails.send({
    from,
    to: args.toEmail,
    replyTo: resendReplyTo(),
    subject,
    html,
    text,
    headers: buildDeliverabilityHeaders({ category: 'visit_pdf' }),
    attachments: [
      {
        filename,
        content: args.pdfBuffer,
      },
    ],
  });

  // Resend returns `{ data: { id }, error }` at runtime; the SDK's types
  // have evolved between versions so we coerce defensively.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const id = ((result as any)?.data?.id as string | undefined) ?? null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const error = (result as any)?.error;
  if (error) {
    const message =
      typeof error === 'string'
        ? error
        : error.message ?? JSON.stringify(error);
    // Classify setup-level errors so callers can show them as a LOUD
    // "email isn't configured" banner rather than a per-message blip.
    // Known Resend setup-error phrases as of 2026-04 — extend the
    // list if Resend reshapes their error messages.
    if (
      /domain is not verified/i.test(message) ||
      /api key.*restricted/i.test(message) ||
      /api key.*invalid/i.test(message) ||
      /from.*not.*allowed/i.test(message)
    ) {
      console.error(
        '[OPS] [email] Resend setup error — email delivery is broken until fixed:',
        message
      );
      throw new EmailNotConfiguredError(
        `Email delivery isn't set up on this deployment: ${message}. Contact the admin.`
      );
    }
    throw new Error(`Resend rejected the message: ${message}`);
  }
  // Phase 6Z (PHASE-6Z-07): one usage row per successful send. We don't
  // know userId/practiceId at this layer (callers don't pass them),
  // so the row attributes only by provider. Fire-and-forget — the
  // logApiUsage internals never throw.
  logApiUsage(
    buildResendUsage(
      { metadata: { kind: 'visit_pdf', visitId: args.visitId } },
      1
    )
  );
  return { id, toEmail: args.toEmail };
}

// ============================================================================
// T-M16.2 — transactional auth emails
// ----------------------------------------------------------------------------
// Five new senders for the HIPAA trio + email verification work. All
// follow the same shape as sendVisitPdfEmail: getClient() throws
// EmailNotConfiguredError when RESEND_API_KEY is unset, Resend 4xx/5xx
// errors get classified by keyword so ops sees a LOUD config alarm
// instead of a per-message blip.
//
// Keep these text-first: patient-free content so every sender can fall
// back to a plain-text-only copy in a pinch. Short HTML is a nicety,
// not load-bearing.
// ============================================================================

interface SenderResult {
  id: string | null;
  toEmail: string;
}

function resendFrom(): string {
  return process.env.RESEND_FROM?.trim() || DEFAULT_FROM;
}

/** Reply-To address. Defaults to support@quillmd.com so doctor replies
 *  go to a real inbox instead of bouncing off `noreply@`. Override via
 *  RESEND_REPLY_TO in .env (e.g., for a per-tenant routing inbox). */
const DEFAULT_REPLY_TO = 'support@quillmd.com';

function resendReplyTo(): string {
  return process.env.RESEND_REPLY_TO?.trim() || DEFAULT_REPLY_TO;
}

/** Public-facing app URL used as the unsubscribe destination. Mirrors
 *  the same fallback chain Auth.js uses. Forces https: because Gmail
 *  silently ignores `List-Unsubscribe` URLs that aren't https — if a
 *  dev override (e.g., AUTH_URL=http://localhost:3000) ever reached
 *  production mail, we'd be quietly degrading deliverability. */
function appUrl(): string {
  const raw =
    process.env.AUTH_URL?.replace(/\/$/, '') ?? 'https://app.quillmd.com';
  if (!raw.startsWith('https://')) return 'https://app.quillmd.com';
  return raw;
}

/** Headers every transactional email carries. Two deliverability wins
 *  here, both 2026-05-13 audit follow-ups:
 *
 *  - **List-Unsubscribe** + **List-Unsubscribe-Post** (RFC 8058): even
 *    on transactional mail, Microsoft Exchange Online / Outlook 365
 *    treat absence as a yellow flag. Including `mailto:` AND `https://`
 *    options gives every receiver a path they understand. The
 *    one-click `List-Unsubscribe-Post` header tells Gmail/Yahoo this
 *    sender supports their one-click unsubscribe button.
 *
 *  - **X-Entity-Ref-ID**: opaque correlation token, helps the receiver
 *    distinguish per-message threads (some filters use it to dedupe).
 *    A short random ID per send.
 *
 *  Exported for unit testing — sendOne and sendVisitPdfEmail are the
 *  intended callers.
 */
export function buildDeliverabilityHeaders(args: {
  /** Short slug identifying which transactional template this is.
   *  Used to scope the unsubscribe URL so the operator can correlate
   *  which template a click came from. */
  category: string;
}): Record<string, string> {
  const replyTo = resendReplyTo();
  const unsubMailto = `mailto:${replyTo}?subject=Unsubscribe%20${encodeURIComponent(
    args.category,
  )}`;
  const unsubUrl = `${appUrl()}/api/email/unsubscribe?category=${encodeURIComponent(
    args.category,
  )}`;
  return {
    'List-Unsubscribe': `<${unsubMailto}>, <${unsubUrl}>`,
    'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    'X-Entity-Ref-ID': randomRefId(),
  };
}

function randomRefId(): string {
  // 96 bits of randomness, base36; ~20 chars. Not cryptographically
  // load-bearing — just an opaque correlation ID per send.
  let out = '';
  for (let i = 0; i < 4; i++) {
    out += Math.random().toString(36).slice(2, 10);
  }
  return out.slice(0, 20);
}

async function sendOne(args: {
  to: string;
  subject: string;
  html: string;
  text: string;
  /** Short slug identifying which transactional template this is.
   *  Used in the List-Unsubscribe URL so an unsubscribe click can
   *  scope to the category (verification, reset, etc.). */
  category: string;
}): Promise<SenderResult> {
  const client = getClient();
  const result = await client.emails.send({
    from: resendFrom(),
    to: args.to,
    replyTo: resendReplyTo(),
    subject: args.subject,
    html: args.html,
    text: args.text,
    headers: buildDeliverabilityHeaders({ category: args.category }),
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const id = ((result as any)?.data?.id as string | undefined) ?? null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const error = (result as any)?.error;
  if (error) {
    const message =
      typeof error === 'string'
        ? error
        : error.message ?? JSON.stringify(error);
    if (
      /domain is not verified/i.test(message) ||
      /api key.*restricted/i.test(message) ||
      /api key.*invalid/i.test(message) ||
      /from.*not.*allowed/i.test(message)
    ) {
      console.error(
        '[OPS] [email] Resend setup error — email delivery is broken until fixed:',
        message
      );
      throw new EmailNotConfiguredError(
        `Email delivery isn't set up on this deployment: ${message}. Contact the admin.`
      );
    }
    throw new Error(`Resend rejected the message: ${message}`);
  }
  // Phase 6Z (PHASE-6Z-07): track the auth/account email send in
  // api_usage_events. Same caveat as sendVisitPdfEmail — no userId
  // attribution from this layer. Subject is captured in metadata for
  // operator-facing diagnostics.
  logApiUsage(
    buildResendUsage(
      { metadata: { kind: 'transactional', subject: args.subject } },
      1
    )
  );
  return { id, toEmail: args.to };
}

function greetingFor(name: string | null | undefined): string {
  const trimmed = name?.trim();
  return trimmed ? `Hi ${trimmed},` : 'Hi,';
}

// ---------------------------------------------------------------------------
// Note format certified — one-time nudge when a doctor's uploaded note format
// finishes verification and becomes the active format for its visit type.
// Plain, human copy; no internal jargon (no "twin"/"IR"/"mapping"/"compiled");
// links to the note-format settings page. Fired only on the CERTIFIED
// transition by the certify action, and only when email delivery is enabled.
// ---------------------------------------------------------------------------

export interface SendTemplateCertifiedArgs {
  toEmail: string;
  userName: string | null;
  templateName: string;
}

export async function sendTemplateCertifiedEmail(
  args: SendTemplateCertifiedArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const manageUrl = `${appUrl()}/settings/note-format`;
  const rawName = args.templateName.trim() || 'Your note format';
  const subject = 'Your note format is ready to use';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Good news — <strong>${escapeHtml(rawName)}</strong> is set up and ready. From now on, QuillMD will format your notes for that visit type to match it.</p>`,
    `<p>There's nothing else you need to do. You can review it, or switch formats, any time from your settings:</p>`,
    `<p><a href="${manageUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Open note format settings</a></p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · note formats</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    `Good news — "${rawName}" is set up and ready. From now on, QuillMD will format your notes for that visit type to match it.`,
    '',
    "There's nothing else you need to do. Review it, or switch formats, any time from your settings:",
    '',
    manageUrl,
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'template_certified' });
}

// ---------------------------------------------------------------------------
// Password reset
// ---------------------------------------------------------------------------

export interface SendPasswordResetArgs {
  toEmail: string;
  resetUrl: string;
  userName: string | null;
}

export async function sendPasswordResetEmail(
  args: SendPasswordResetArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const subject = 'Reset your QuillMD password';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Someone (hopefully you) asked to reset the password on your QuillMD account. Click the link below to set a new one:</p>`,
    `<p><a href="${args.resetUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Reset my password</a></p>`,
    `<p style="color:#666;font-size:13px;">The link expires in 1 hour and can only be used once. If you didn't request this, you can safely ignore this email — your password stays the same.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    'Someone asked to reset the password on your QuillMD account. Open this link to set a new one:',
    '',
    args.resetUrl,
    '',
    "The link expires in 1 hour and can only be used once. If you didn't request this, ignore this email — your password stays the same.",
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'password_reset' });
}

// ---------------------------------------------------------------------------
// Email verification (signup)
// ---------------------------------------------------------------------------

export interface SendEmailVerificationArgs {
  toEmail: string;
  verifyUrl: string;
  userName: string | null;
}

export async function sendEmailVerification(
  args: SendEmailVerificationArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const subject = 'Verify your QuillMD email';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Welcome to QuillMD. Please confirm this email address so we know we can reach you:</p>`,
    `<p><a href="${args.verifyUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Verify my email</a></p>`,
    `<p style="color:#666;font-size:13px;">The link expires in 24 hours. If you didn't sign up for QuillMD, you can ignore this email.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    'Welcome to QuillMD. Please confirm this email address by opening the link below:',
    '',
    args.verifyUrl,
    '',
    "The link expires in 24 hours. If you didn't sign up for QuillMD, you can ignore this email.",
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'verify_email' });
}

// ---------------------------------------------------------------------------
// Round 3 PR-F (A02-P1-001) — signup anti-enumeration: "you already have an
// account" email sent in lieu of verification when signup hits an existing
// email. Same 200/redirect response goes to the signup form regardless;
// the real account holder receives this nudge so they aren't left thinking
// their signup attempt vanished. An attacker probing for existing accounts
// sees the same 200 + same response timing + no inbox feedback.
// ---------------------------------------------------------------------------

export interface SendAccountExistsArgs {
  toEmail: string;
  userName: string | null;
  signInUrl: string;
}

export async function sendAccountExistsEmail(
  args: SendAccountExistsArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const subject = 'You already have a QuillMD account';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Someone (hopefully you) just tried to sign up for QuillMD with this email — but you already have an account here. There's no new account to verify; just sign in with the password you set when you first registered:</p>`,
    `<p><a href="${args.signInUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Sign in</a></p>`,
    `<p style="color:#666;font-size:13px;">If you don't remember your password, use the "Forgot password" link on the sign-in page. If you didn't try to sign up, you can safely ignore this email — your account is unchanged.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    "Someone (hopefully you) just tried to sign up for QuillMD with this email — but you already have an account. Sign in with the password you set when you first registered:",
    '',
    args.signInUrl,
    '',
    'If you don\'t remember your password, use the "Forgot password" link on the sign-in page. If you didn\'t try to sign up, you can safely ignore this email.',
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'account_exists' });
}

// ---------------------------------------------------------------------------
// Email change — confirm link sent to the NEW address
// ---------------------------------------------------------------------------

export interface SendEmailChangeRequestArgs {
  toEmail: string;
  confirmUrl: string;
  userName: string | null;
}

export async function sendEmailChangeRequestEmail(
  args: SendEmailChangeRequestArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const subject = 'Confirm your new QuillMD email';
  const html = [
    `<p>${greeting}</p>`,
    `<p>You asked to change the email address on your QuillMD account to this one. Click below to confirm:</p>`,
    `<p><a href="${args.confirmUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Confirm new email</a></p>`,
    `<p style="color:#666;font-size:13px;">The link expires in 24 hours. Until you confirm, you'll keep signing in with your old email. If you didn't request this change, ignore this email.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    'You asked to change the email address on your QuillMD account to this one. Confirm by opening the link below:',
    '',
    args.confirmUrl,
    '',
    "The link expires in 24 hours. Until you confirm, you'll keep signing in with your old email. If you didn't request this change, ignore this email.",
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'email_change_request' });
}

// ---------------------------------------------------------------------------
// Email change — heads-up sent to the OLD address after confirmation
// ---------------------------------------------------------------------------

export interface SendEmailChangedNotificationArgs {
  toEmail: string;
  newEmail: string;
  userName: string | null;
}

export async function sendEmailChangedNotification(
  args: SendEmailChangedNotificationArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const subject = 'Your QuillMD email was changed';
  const html = [
    `<p>${greeting}</p>`,
    `<p>The email address on your QuillMD account was just changed to <strong>${args.newEmail}</strong>.</p>`,
    `<p style="color:#666;font-size:13px;">If you made this change, nothing else is required. If you didn't, reply to this email from <em>this</em> address immediately — we can roll it back before the session expires.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    `The email address on your QuillMD account was just changed to ${args.newEmail}.`,
    '',
    "If you made this change, nothing else is required. If you didn't, reply to this email from THIS address immediately — we can roll it back before the session expires.",
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'email_changed_notification' });
}

// ---------------------------------------------------------------------------
// Account deletion — final heads-up to the deleted user's email
// ---------------------------------------------------------------------------

export interface SendAccountDeletedArgs {
  toEmail: string;
  userName: string | null;
}

export async function sendAccountDeletedConfirmation(
  args: SendAccountDeletedArgs
): Promise<SenderResult> {
  const greeting = greetingFor(args.userName);
  const subject = 'Your QuillMD account was deleted';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Your QuillMD account and all associated data have been deleted. This can't be undone.</p>`,
    `<p style="color:#666;font-size:13px;">We keep a minimal compliance record (email, deletion date, visit count at deletion time) for 90 days and then erase that too. If you ever want to come back, you can sign up again from scratch.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">QuillMD · goodbye</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    "Your QuillMD account and all associated data have been deleted. This can't be undone.",
    '',
    'We keep a minimal compliance record (email, deletion date, visit count) for 90 days, then erase that too. If you ever want to come back, you can sign up again from scratch.',
    '',
    '— QuillMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text, category: 'account_deleted' });
}
