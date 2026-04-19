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

import { NextResponse } from 'next/server';
import { z } from 'zod';

import { auth } from '@/lib/nextauth';
import { formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { generateVisitPdf } from '@/lib/pdf-generator';
import { sendVisitPdfEmail } from '@/lib/email';
import { logDelivery } from '@/lib/deliveries';

import { apiError, withApiHandler } from '@/lib/api-error';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const BodySchema = z.object({
  to: z.string().email().optional(),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:export:email',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    const sessionEmail = session?.user?.email;
    if (!userId || !sessionEmail) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid email address', 400);

    const toEmail = parsed.data.to ?? sessionEmail;

    const data = await loadVisitExportData(visitId, userId);
    if (!data) return apiError('not found', 404);

    if (!process.env.RESEND_API_KEY) {
      // Fail softly rather than throwing a stack at the client. The
      // Sign & Send modal's T-M9 error-classification logic turns
      // this into a loud "email delivery not configured" toast.
      return apiError(
        'email delivery is not configured on this environment',
        503
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
      console.error('[api:visits:export:email] send failed:', err);
      return apiError(
        'email delivery failed — try again or download the PDF instead',
        502
      );
    }
  }
);
