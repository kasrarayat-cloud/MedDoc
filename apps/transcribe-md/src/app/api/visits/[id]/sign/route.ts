// ============================================================================
// POST /api/visits/[id]/sign (T-M7)
// ----------------------------------------------------------------------------
// Replaces the old T-M4 signVisitAction with a unified sign + deliver
// path. Accepts a multi-destination body so the doctor can, in one
// click, freeze the note AND paste-to-Epic AND email themselves AND
// download the PDF.
//
// Body: {
//   destinations: Array<
//     | 'clipboard_epic' | 'clipboard_athena' | 'clipboard_cerner'
//     | 'clipboard_eclinicalworks' | 'clipboard_generic'
//     | 'pdf' | 'docx' | 'email'
//   >,
//   emailTo?: string
// }
//
// Response: {
//   signedAt: ISO,
//   clipboardTexts?: Record<clipboard_format, string>,
//   pdfDownloadUrl?: string,   // "/api/visits/:id/export/pdf"
//   docxDownloadUrl?: string,
//   emailQueued?: boolean
// }
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { formatForEhr, type EhrFormat } from '@/lib/ehr-formatters';
import { generateVisitPdf } from '@/lib/pdf-generator';
import { sendVisitPdfEmail } from '@/lib/email';
import {
  logDelivery,
  type DeliveryChannel,
} from '@/lib/deliveries';
import { captureEditPattern } from '@/lib/edit-tracking';

import { apiError, withApiHandler } from '@/lib/api-error';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const Destination = z.enum([
  'clipboard_epic',
  'clipboard_athena',
  'clipboard_cerner',
  'clipboard_eclinicalworks',
  'clipboard_generic',
  'pdf',
  'docx',
  'email',
]);

const BodySchema = z.object({
  destinations: z.array(Destination).max(10).default([]),
  emailTo: z.string().email().optional(),
});

const FORMAT_FOR_CHANNEL: Partial<
  Record<z.infer<typeof Destination>, EhrFormat>
> = {
  clipboard_epic: 'epic',
  clipboard_athena: 'athena',
  clipboard_cerner: 'cerner',
  clipboard_eclinicalworks: 'eclinicalworks',
  clipboard_generic: 'generic',
};

export const POST = withApiHandler<{ id: string }>(
  'api:visits:sign',
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
    if (!parsed.success) return apiError('invalid destinations payload', 400);

    // ── Sign ────────────────────────────────────────────────────────
    // Use an atomic updateMany with a status guard so two concurrent
    // submissions can't both "win" and double-sign.
    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        status: true,
        soapFinal: true,
        signedAt: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (
      visit.status !== TranscribeVisitStatus.READY &&
      visit.status !== TranscribeVisitStatus.SIGNED
    ) {
      return apiError('visit is still processing', 409);
    }
    if (!visit.soapFinal?.trim()) {
      return apiError('visit has no SOAP to sign', 409);
    }

    let signedAt = visit.signedAt;
    if (visit.status === TranscribeVisitStatus.READY) {
      const updated = await prisma.transcribeVisit.updateMany({
        where: {
          id: visitId,
          status: TranscribeVisitStatus.READY,
        },
        data: {
          status: TranscribeVisitStatus.SIGNED,
          signedSoap: visit.soapFinal,
          signedAt: new Date(),
        },
      });
      if (updated.count === 0) {
        // Another concurrent request got there first. Re-read.
        const refreshed = await prisma.transcribeVisit.findUnique({
          where: { id: visitId },
          select: { signedAt: true, status: true },
        });
        if (refreshed?.status !== TranscribeVisitStatus.SIGNED) {
          return apiError('sign race lost — please refresh and retry', 409);
        }
        signedAt = refreshed.signedAt;
      } else {
        const refreshed = await prisma.transcribeVisit.findUnique({
          where: { id: visitId },
          select: { signedAt: true },
        });
        signedAt = refreshed?.signedAt ?? new Date();
        // T-M14.1: fire-and-forget edit-pattern capture. Only on the
        // winning transition — race losers already have a capture in
        // flight from the winner's handler, and the @unique visitId
        // constraint would reject a second insert anyway.
        void captureEditPattern({ visitId, doctorId: userId });
      }
    }

    // ── Deliver ─────────────────────────────────────────────────────
    // loadVisitExportData reads the freshly-signed row so downstream
    // generators see signedSoap / signedAt set correctly.
    const data = await loadVisitExportData(visitId, userId);
    if (!data) return apiError('visit disappeared after signing', 500);

    const clipboardTexts: Record<string, string> = {};
    let pdfDownloadUrl: string | undefined;
    let docxDownloadUrl: string | undefined;
    let emailQueued = false;
    // Track which destinations actually succeeded vs which soft-failed so
    // the client can tell the user specifically what didn't go through.
    const deliveryErrors: Record<string, string> = {};

    for (const dest of parsed.data.destinations) {
      const channel: DeliveryChannel = dest;
      try {
        if (dest === 'pdf') {
          // The browser does the actual download; we return a URL so the
          // JSON response stays small. We still log here — the user
          // explicitly requested a PDF delivery, and the dedicated route
          // will log again when they fetch. Two rows is fine; it
          // reflects intent + completion.
          pdfDownloadUrl = `/api/visits/${visitId}/export/pdf`;
          logDelivery({ visitId, channel });
        } else if (dest === 'docx') {
          docxDownloadUrl = `/api/visits/${visitId}/export/docx`;
          logDelivery({ visitId, channel });
        } else if (dest === 'email') {
          if (!process.env.RESEND_API_KEY) {
            deliveryErrors[dest] =
              'email delivery is not configured on this environment';
            continue;
          }
          const to = parsed.data.emailTo ?? sessionEmail;
          const pdf = await generateVisitPdf(data);
          await sendVisitPdfEmail({
            toEmail: to,
            visitId,
            pdfBuffer: pdf,
            doctorName: data.clinicianName,
            patientName: data.patientName,
            visitDate: formatVisitDate(data.signedAt ?? data.createdAt),
          });
          emailQueued = true;
          logDelivery({
            visitId,
            channel,
            destination: to,
            sizeBytes: pdf.byteLength,
          });
        } else {
          const format = FORMAT_FOR_CHANNEL[dest];
          if (!format) continue;
          const text = formatForEhr(format, data);
          clipboardTexts[dest] = text;
          logDelivery({
            visitId,
            channel,
            sizeBytes: Buffer.byteLength(text, 'utf8'),
          });
        }
      } catch (err) {
        console.error(`[api:visits:sign] destination ${dest} failed:`, err);
        deliveryErrors[dest] =
          err instanceof Error ? err.message : 'delivery failed';
      }
    }

    return NextResponse.json(
      {
        signedAt: signedAt?.toISOString() ?? null,
        clipboardTexts,
        pdfDownloadUrl,
        docxDownloadUrl,
        emailQueued,
        deliveryErrors: Object.keys(deliveryErrors).length
          ? deliveryErrors
          : undefined,
      },
      { status: 200 }
    );
  }
);
