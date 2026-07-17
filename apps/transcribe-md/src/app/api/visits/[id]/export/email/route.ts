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

import { NextResponse } from "next/server";
import { z } from "zod";

import { auth } from "@/lib/nextauth";
import { formatVisitDate } from "@/lib/visit-export";
import { loadVisitExportData } from "@/lib/visit-export-server";
import { generateVisitPdf } from "@/lib/pdf-generator";
import { sendVisitPdfEmail } from "@/lib/email";
import { logDelivery } from "@/lib/deliveries";

import { apiError, withApiHandler } from "@/lib/api-error";
import { redactPhi } from "@meddoc/ai";
import { log } from "@/lib/log";
import { logAudit } from "@/lib/audit";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const BodySchema = z.object({
  to: z.string().email().max(254).optional(),
});

export const POST = withApiHandler<{ id: string }>(
  "api:visits:export:email",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    const sessionEmail = session?.user?.email;
    if (!userId || !sessionEmail) return apiError("unauthorized", 401);
    if (
      isTemplateTwinStagingQaRequested() ||
      (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId }))
    ) {
      return apiError("not found", 404);
    }

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError("invalid email address", 400);

    // ── PHI exfiltration guard ─────────────────────────────────────
    // Pre-fix, `body.to` was accepted as-is and passed straight to
    // Resend — letting any session holder mail every signed SOAP to
    // an arbitrary external inbox. Enforce: the destination MUST
    // equal the caller's own account email (case-insensitive). If a
    // future feature wants colleague delivery, register the
    // destination on the Practice and match against that list.
    const toEmail = (parsed.data.to ?? sessionEmail).toLowerCase().trim();
    if (toEmail !== sessionEmail.toLowerCase().trim()) {
      log.warn("api:visits:export:email", "destination blocked", {
        userId,
        visitId,
        requestedDomain: toEmail.split("@")[1] ?? "unknown",
        sessionDomain: sessionEmail.split("@")[1] ?? "unknown",
      });
      void logAudit({
        action: "EXPORT_EMAIL_BLOCKED_DESTINATION",
        targetType: "TranscribeVisit",
        targetId: visitId,
        success: false,
        errorCode: "INVALID_DESTINATION",
        metadata: {
          via: "export/email",
          requestedDomain: toEmail.split("@")[1] ?? "unknown",
          sessionDomain: sessionEmail.split("@")[1] ?? "unknown",
        },
      });
      return apiError("Email destination must match your account email.", 403, {
        code: "INVALID_DESTINATION",
        retry: false,
      });
    }

    const data = await loadVisitExportData(visitId, userId);
    if (!data) return apiError("not found", 404);

    if (!process.env.RESEND_API_KEY) {
      // Fail softly rather than throwing a stack at the client. The
      // Sign & Send modal's T-M9 error-classification logic turns
      // this into a loud "email delivery not configured" toast.
      return apiError(
        "email delivery is not configured on this environment",
        503,
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
        channel: "email",
        destination: toEmail,
        sizeBytes: pdf.byteLength,
      });
      void logAudit({
        action: "EXPORT_EMAIL_SENT",
        targetType: "TranscribeVisit",
        targetId: visitId,
        metadata: {
          sizeBytes: pdf.byteLength,
          // Destination is the session's own email (gated above); OK
          // to record it verbatim since it's already in the users row.
          destinationDomain: toEmail.split("@")[1] ?? "unknown",
        },
      });
      return NextResponse.json(
        { ok: true, messageId: result.id },
        { status: 200 },
      );
    } catch (err) {
      // T-M16.3: Resend error messages quote the recipient address on
      // bounces — scrub before logging.
      console.error(
        "[api:visits:export:email] send failed:",
        redactPhi(err instanceof Error ? err.message : err),
      );
      return apiError(
        "email delivery failed — try again or download the PDF instead",
        502,
      );
    }
  },
);
