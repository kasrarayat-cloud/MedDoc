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

/** From-address defaults to notes@transcribemd.app — that domain MUST
 *  be verified in the Resend account attached to RESEND_API_KEY.
 *  Verify at https://resend.com/domains (needs DNS access). Override
 *  with RESEND_FROM="Name <addr@verified-domain.tld>" if you want to
 *  ship from a different address. */
const DEFAULT_FROM = 'TranscribeMD <notes@transcribemd.app>';

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
