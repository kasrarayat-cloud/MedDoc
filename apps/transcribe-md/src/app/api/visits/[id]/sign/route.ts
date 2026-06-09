// ============================================================================
// POST /api/visits/[id]/sign (T-M7)
// ----------------------------------------------------------------------------
// The unified sign + deliver path (T-M7) — the SOLE path that transitions a
// visit READY→SIGNED. Accepts a multi-destination body so the doctor can, in
// one click, freeze the note AND paste-to-Epic AND email themselves AND
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
import { redactPhi } from '@meddoc/ai';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';
import { criticalWarningRefs } from '@/lib/rx-warnings';

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
  emailTo: z.string().email().max(254).optional(),
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

    // ── PHI exfiltration guard ─────────────────────────────────────
    // If an 'email' destination is requested, `emailTo` MUST match
    // the caller's own account email (case-insensitive). Same guard
    // as /api/visits/[id]/export/email — prevents a session holder
    // from co-delivering every signed SOAP to any external inbox in
    // the same click that signs the visit.
    if (parsed.data.destinations.includes('email')) {
      const requestedTo = (parsed.data.emailTo ?? sessionEmail)
        .toLowerCase()
        .trim();
      if (requestedTo !== sessionEmail.toLowerCase().trim()) {
        log.warn('api:visits:sign', 'email destination blocked', {
          userId,
          visitId,
          requestedDomain: requestedTo.split('@')[1] ?? 'unknown',
          sessionDomain: sessionEmail.split('@')[1] ?? 'unknown',
        });
        void logAudit({
          action: 'EXPORT_EMAIL_BLOCKED_DESTINATION',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          success: false,
          errorCode: 'INVALID_DESTINATION',
          metadata: {
            via: 'sign',
            requestedDomain: requestedTo.split('@')[1] ?? 'unknown',
            sessionDomain: sessionEmail.split('@')[1] ?? 'unknown',
          },
        });
        return apiError(
          'Email destination must match your account email.',
          403,
          { code: 'INVALID_DESTINATION', retry: false }
        );
      }
    }

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
        rxDrafts: true,
        signedAt: true,
        deletedAt: true,
        archivedAt: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    // T-M17.3: never silently sign a trashed / archived visit. Archived
    // SIGNED visits cannot be re-signed via this route — the operator
    // must unarchive first (dedicated flow, not in T-M17.3 scope).
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error: 'Visit is no longer active. Restore it first.',
          code: 'VISIT_NOT_ACTIVE',
        },
        { status: 400 }
      );
    }
    if (
      visit.status !== TranscribeVisitStatus.READY &&
      visit.status !== TranscribeVisitStatus.SIGNED
    ) {
      return apiError('visit is still processing', 409);
    }
    if (!visit.soapFinal?.trim()) {
      return apiError('visit has no SOAP to sign', 409);
    }

    // F5-1 + fix/rx-override-gate-correlation: Critical Rx warnings require a
    // PER-WARNING override before sign. Pre-F5-1 the endpoint accepted the
    // transition without checking (the override modal was UI-only, so direct/
    // scripted callers bypassed it). F5-1 added a server gate but compared a
    // BARE COUNT of severity='critical' override rows against the critical-
    // warning count — which a caller could satisfy by minting fabricated/
    // duplicate 'critical' rows. The gate now clears the READY→SIGNED
    // transition ONLY when EVERY persisted critical warning has a matching
    // override keyed by its REAL id (rx-warning-<index>). recordOverride
    // validates the id+severity against rxDrafts on write; this coverage check
    // is the second line of defence at sign time. Already-SIGNED visits skip
    // the gate; it fires on the READY → SIGNED transition only.
    if (visit.status === TranscribeVisitStatus.READY) {
      const criticalRefs = criticalWarningRefs(visit.rxDrafts);
      if (criticalRefs.length > 0) {
        const overrideRows = await prisma.rxWarningOverride.findMany({
          where: { visitId, severity: 'critical' },
          select: { warningId: true },
        });
        const overriddenIds = new Set(
          overrideRows.map((o: { warningId: string }) => o.warningId)
        );
        const unmet = criticalRefs.filter((ref) => !overriddenIds.has(ref.id));
        if (unmet.length > 0) {
          log.warn('api:visits:sign', 'override required', {
            userId,
            visitId,
            criticalCount: criticalRefs.length,
            overriddenCount: overriddenIds.size,
            unmetCount: unmet.length,
          });
          void logAudit({
            action: 'RX_SIGN_BLOCKED_NO_OVERRIDE',
            targetType: 'TranscribeVisit',
            targetId: visitId,
            success: false,
            errorCode: 'OVERRIDE_REQUIRED',
            metadata: {
              criticalCount: criticalRefs.length,
              overriddenCount: overriddenIds.size,
              unmetCount: unmet.length,
            },
          });
          return NextResponse.json(
            {
              error: 'Critical Rx warnings require an override before signing.',
              code: 'OVERRIDE_REQUIRED',
              warnings: unmet.map((ref) => ({
                severity: 'critical',
                drug: ref.warning.rx_drug ?? '',
                message: ref.warning.message ?? '',
                warningId: ref.id,
              })),
            },
            { status: 422 }
          );
        }
      }
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
        // HIPAA audit — one row per successful READY→SIGNED transition.
        // Race losers (updated.count===0) don't re-write; the winner
        // already covered them.
        void logAudit({
          action: 'VISIT_SIGNED',
          targetType: 'TranscribeVisit',
          targetId: visitId,
          metadata: {
            destinations: parsed.data.destinations,
          },
        });
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
          // Guard above already enforced emailTo === sessionEmail
          // when present. Resolve to sessionEmail explicitly to
          // close the loop for any future refactor of the guard.
          const to = sessionEmail;
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
        // T-M16.3: Resend/MinIO/PDF errors occasionally echo recipient
        // email or filename — scrub before logging.
        console.error(
          `[api:visits:sign] destination ${dest} failed:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
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
