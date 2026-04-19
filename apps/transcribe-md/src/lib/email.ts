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

let clientSingleton: Resend | null = null;

function getClient(): Resend {
  if (clientSingleton) return clientSingleton;
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    throw new Error(
      'RESEND_API_KEY is not set. Add it to .env before enabling email delivery.'
    );
  }
  clientSingleton = new Resend(apiKey);
  return clientSingleton;
}

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
    throw new Error(
      `Resend rejected the message: ${
        typeof error === 'string' ? error : error.message ?? JSON.stringify(error)
      }`
    );
  }
  return { id, toEmail: args.toEmail };
}
