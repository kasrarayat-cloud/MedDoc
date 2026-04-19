// ============================================================================
// POST /api/visits/[id]/export/email (T-M7)
// ----------------------------------------------------------------------------
// Body: { to?: string }  — defaults to session.user.email.
// Sends a PDF via Resend. Logs a VisitDelivery row.
// Doctor-only delivery path. Don't accept patient emails here — the
// Sign & Send modal pre-fills session.user.email and the input shape
// only permits one address so the doctor has to type their own (or a
// colleague's) rather than a patient's by mistake.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import { z } from 'zod';

import { auth } from '@/lib/nextauth';
import { formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { generateVisitPdf } from '@/lib/pdf-generator';
import { sendVisitPdfEmail } from '@/lib/email';
import { logDelivery } from '@/lib/deliveries';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const BodySchema = z.object({
  to: z.string().email().optional(),
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: visitId } = await params;

  const session = await auth();
  const userId = session?.user?.id;
  const sessionEmail = session?.user?.email;
  if (!userId || !sessionEmail) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'invalid email address' },
      { status: 400 }
    );
  }

  const toEmail = parsed.data.to ?? sessionEmail;

  const data = await loadVisitExportData(visitId, userId);
  if (!data) {
    return NextResponse.json({ error: 'not found' }, { status: 404 });
  }

  if (!process.env.RESEND_API_KEY) {
    // Fail softly rather than returning a stack trace to the client.
    // The Sign & Send modal can catch this and show a toast.
    return NextResponse.json(
      { error: 'email delivery is not configured on this environment' },
      { status: 503 }
    );
  }

  const pdf = await generateVisitPdf(data);
  try {
    const result = await sendVisitPdfEmail({
      toEmail,
      visitId,
      pdfBuffer: pdf,
      doctorName: data.clinicianName,
      patientName: data.patientName,
      visitDate: formatVisitDate(data.signedAt ?? data.createdAt),
    });
    logDelivery({
      visitId,
      channel: 'email',
      destination: toEmail,
      sizeBytes: pdf.byteLength,
    });
    return NextResponse.json(
      { ok: true, messageId: result.id },
      { status: 200 }
    );
  } catch (err) {
    console.error('[email-export] send failed:', err);
    return NextResponse.json(
      {
        error:
          'email delivery failed — try again or download the PDF instead',
      },
      { status: 502 }
    );
  }
}
