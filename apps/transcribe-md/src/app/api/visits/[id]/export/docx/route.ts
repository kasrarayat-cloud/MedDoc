// ============================================================================
// GET /api/visits/[id]/export/docx (T-M7)
// ----------------------------------------------------------------------------
// Same shape as the PDF route; different generator + Content-Type.
// ============================================================================

import { NextResponse } from "next/server";

import { auth } from "@/lib/nextauth";
import { filenameSlug, formatVisitDate } from "@/lib/visit-export";
import { loadVisitExportData } from "@/lib/visit-export-server";
import { generateVisitDocx } from "@/lib/docx-generator";
import { logDelivery } from "@/lib/deliveries";

import { apiError, withApiHandler } from "@/lib/api-error";
import { redactPhi } from "@meddoc/ai";
import { logAudit } from "@/lib/audit";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export const GET = withApiHandler<{ id: string }>(
  "api:visits:export:docx",
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    const data = await loadVisitExportData(visitId, userId);
    if (!data) return apiError("not found", 404);

    let docx: Buffer;
    try {
      docx = await generateVisitDocx(data);
    } catch (err) {
      console.error(
        "[api:visits:export:docx] generation failed:",
        redactPhi(err instanceof Error ? err.message : err),
      );
      return apiError("docx generation failed", 500);
    }

    logDelivery({
      visitId,
      channel: "docx",
      sizeBytes: docx.byteLength,
    });
    void logAudit({
      action: "EXPORT_DOCX_DOWNLOADED",
      targetType: "TranscribeVisit",
      targetId: visitId,
      metadata: {
        sizeBytes: docx.byteLength,
        isSigned: data.signedAt !== null,
      },
    });

    const filename = `visit-${filenameSlug(data.patientName)}-${formatVisitDate(
      data.signedAt ?? data.createdAt,
    )}.docx`;

    return new NextResponse(docx as unknown as BodyInit, {
      status: 200,
      headers: {
        "Content-Type": DOCX_MIME,
        "Content-Length": String(docx.byteLength),
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store, private",
      },
    });
  },
);
