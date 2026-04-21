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
  const subject = `Your TranscribeMD visit note${subjectTail}`;
  const greeting = args.doctorName?.trim()
    ? `Hi ${args.doctorName.trim()},`
    : 'Hi,';

  const html = [
    `<p>${greeting}</p>`,
    `<p>Your signed visit note is attached as a PDF.</p>`,
    `<p style="color:#666;font-size:13px;">This email is for your records. Do not forward to patients — TranscribeMD does not handle patient-facing delivery yet. For patient hand-off, download the PDF and share through your usual secure channel.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">TranscribeMD · signed ${args.visitDate}</p>`,
  ].join('\n');

  const text = [
    greeting,
    '',
    'Your signed visit note is attached as a PDF.',
    '',
    'This email is for your records. Do not forward to patients — TranscribeMD does not handle patient-facing delivery yet. For patient hand-off, download the PDF and share through your usual secure channel.',
    '',
    `—`,
    `TranscribeMD · signed ${args.visitDate}`,
  ].join('\n');

  const filename = `visit-${args.visitId}-${args.visitDate}.pdf`;

  const result = await client.emails.send({
    from,
    to: args.toEmail,
    subject,
    html,
    text,
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

async function sendOne(args: {
  to: string;
  subject: string;
  html: string;
  text: string;
}): Promise<SenderResult> {
  const client = getClient();
  const result = await client.emails.send({
    from: resendFrom(),
    to: args.to,
    subject: args.subject,
    html: args.html,
    text: args.text,
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
  return { id, toEmail: args.to };
}

function greetingFor(name: string | null | undefined): string {
  const trimmed = name?.trim();
  return trimmed ? `Hi ${trimmed},` : 'Hi,';
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
  const subject = 'Reset your TranscribeMD password';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Someone (hopefully you) asked to reset the password on your TranscribeMD account. Click the link below to set a new one:</p>`,
    `<p><a href="${args.resetUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Reset my password</a></p>`,
    `<p style="color:#666;font-size:13px;">The link expires in 1 hour and can only be used once. If you didn't request this, you can safely ignore this email — your password stays the same.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">TranscribeMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    'Someone asked to reset the password on your TranscribeMD account. Open this link to set a new one:',
    '',
    args.resetUrl,
    '',
    "The link expires in 1 hour and can only be used once. If you didn't request this, ignore this email — your password stays the same.",
    '',
    '— TranscribeMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text });
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
  const subject = 'Verify your TranscribeMD email';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Welcome to TranscribeMD. Please confirm this email address so we know we can reach you:</p>`,
    `<p><a href="${args.verifyUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Verify my email</a></p>`,
    `<p style="color:#666;font-size:13px;">The link expires in 24 hours. If you didn't sign up for TranscribeMD, you can ignore this email.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">TranscribeMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    'Welcome to TranscribeMD. Please confirm this email address by opening the link below:',
    '',
    args.verifyUrl,
    '',
    "The link expires in 24 hours. If you didn't sign up for TranscribeMD, you can ignore this email.",
    '',
    '— TranscribeMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text });
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
  const subject = 'Confirm your new TranscribeMD email';
  const html = [
    `<p>${greeting}</p>`,
    `<p>You asked to change the email address on your TranscribeMD account to this one. Click below to confirm:</p>`,
    `<p><a href="${args.confirmUrl}" style="display:inline-block;padding:10px 18px;background:#7C3AED;color:#fff;border-radius:6px;text-decoration:none;">Confirm new email</a></p>`,
    `<p style="color:#666;font-size:13px;">The link expires in 24 hours. Until you confirm, you'll keep signing in with your old email. If you didn't request this change, ignore this email.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">TranscribeMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    'You asked to change the email address on your TranscribeMD account to this one. Confirm by opening the link below:',
    '',
    args.confirmUrl,
    '',
    "The link expires in 24 hours. Until you confirm, you'll keep signing in with your old email. If you didn't request this change, ignore this email.",
    '',
    '— TranscribeMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text });
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
  const subject = 'Your TranscribeMD email was changed';
  const html = [
    `<p>${greeting}</p>`,
    `<p>The email address on your TranscribeMD account was just changed to <strong>${args.newEmail}</strong>.</p>`,
    `<p style="color:#666;font-size:13px;">If you made this change, nothing else is required. If you didn't, reply to this email from <em>this</em> address immediately — we can roll it back before the session expires.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">TranscribeMD · account security</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    `The email address on your TranscribeMD account was just changed to ${args.newEmail}.`,
    '',
    "If you made this change, nothing else is required. If you didn't, reply to this email from THIS address immediately — we can roll it back before the session expires.",
    '',
    '— TranscribeMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text });
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
  const subject = 'Your TranscribeMD account was deleted';
  const html = [
    `<p>${greeting}</p>`,
    `<p>Your TranscribeMD account and all associated data have been deleted. This can't be undone.</p>`,
    `<p style="color:#666;font-size:13px;">We keep a minimal compliance record (email, deletion date, visit count at deletion time) for 90 days and then erase that too. If you ever want to come back, you can sign up again from scratch.</p>`,
    `<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />`,
    `<p style="color:#999;font-size:12px;">TranscribeMD · goodbye</p>`,
  ].join('\n');
  const text = [
    greeting,
    '',
    "Your TranscribeMD account and all associated data have been deleted. This can't be undone.",
    '',
    'We keep a minimal compliance record (email, deletion date, visit count) for 90 days, then erase that too. If you ever want to come back, you can sign up again from scratch.',
    '',
    '— TranscribeMD',
  ].join('\n');
  return sendOne({ to: args.toEmail, subject, html, text });
}
