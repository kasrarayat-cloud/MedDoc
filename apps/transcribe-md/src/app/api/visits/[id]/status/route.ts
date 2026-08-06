// ============================================================================
// GET /api/visits/[id]/status (T-M4)
// ----------------------------------------------------------------------------
// Polled by the AudioUploader once an upload lands and by the
// /visits/[id] "Processing…" screen. Returns the current status and a
// human-readable progress hint so the UI can show a phase label
// without owning the enum → phrase mapping.
// ============================================================================

import { NextResponse } from 'next/server';

import { getSession } from '@/lib/auth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { parseSoapSections } from '@/lib/parse-soap-sections';

// Truncation budget for SOAP-section preview. Sized from the live
// READY-visit distribution (P95 per-section = 2,661 chars). The 3200
// cap captures P95 with headroom; per-poll payload is ~14 KB which is
// fine for the 1.5s cadence. Transcript preview was dropped — see the
// matching note in processing-typewriter.tsx.
const PREVIEW_SOAP_SECTION_MAX = 3200;

function clipForPreview(text: string | null | undefined, max: number): string | null {
  if (!text) return null;
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (trimmed.length <= max) return trimmed;
  // Soft-break on a word boundary near max so the typewriter doesn't
  // freeze mid-word with the truncation ellipsis.
  const slice = trimmed.slice(0, max);
  const lastSpace = slice.lastIndexOf(' ');
  const boundary = lastSpace > max * 0.7 ? lastSpace : max;
  return trimmed.slice(0, boundary).trimEnd() + '…';
}

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** Enum-driven label for the polling UI. Kept in sync with the 6-layer
 *  sequence so the user can see which step is running. */
const PROGRESS_HINT: Record<TranscribeVisitStatus, string> = {
  QUEUED: 'Queued — waiting for a worker',
  TRANSCRIBING: 'Transcribing audio',
  EXTRACTING: 'Identifying speakers and extracting medical entities',
  DRAFTING: 'Drafting the SOAP note',
  CRITIQUING: 'Auditing the draft for clinical accuracy',
  POLISHING: 'Applying polish fixes',
  AUTOMATING: 'Generating codes, prescriptions, and summary',
  READY: 'Ready to review',
  FAILED: 'Processing failed',
  SIGNED: 'Signed and locked',
};

export const GET = withApiHandler<{ id: string }>(
  'api:visits:status',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        status: true,
        needsReview: true,
        reviewReason: true,
        audioDurationSec: true,
        // T-M18.3 A21: include lifecycle fields so a polling UI whose
        // visit was trashed/archived in another tab can detect it and
        // redirect to /dashboard instead of spinning indefinitely.
        deletedAt: true,
        archivedAt: true,
        // Typewriter processing screen: needs the start anchor for the
        // elapsed clock + the JSONB columns to compute chip counts at
        // the AUTOMATING phase. processingStartedAt is set when L1
        // begins; null on QUEUED rows.
        processingStartedAt: true,
        icdCodes: true,
        cptCodes: true,
        // Preview content for typewriter rendering. soapDraft lands
        // after DRAFTING (overwritten by POLISHING). Server-side
        // truncation keeps polling payload bounded.
        soapDraft: true,
      },
    });
    // 404 on both "not found" AND "not yours" prevents ID enumeration.
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    const status = visit.status as TranscribeVisitStatus;

    // Count chips without leaking the underlying jsonb shape to the
    // client. {codes: [...]} on both ICD + CPT (Phase 5.2 contract);
    // tolerate older rows whose blob may be null or a different shape
    // by defaulting to 0.
    const icdBlob = visit.icdCodes as { codes?: unknown[] } | null;
    const cptBlob = visit.cptCodes as { codes?: unknown[] } | null;
    const icdCount = Array.isArray(icdBlob?.codes) ? icdBlob.codes.length : 0;
    const cptCount = Array.isArray(cptBlob?.codes) ? cptBlob.codes.length : 0;

    // Build typewriter preview content. SOAP markdown is split via the
    // existing parseSoapSections parser used by SoapBody / soap-editor /
    // em-coding to keep the section-split logic single-source.
    let previewSoap: {
      subjective: string | null;
      objective: string | null;
      assessment: string | null;
      plan: string | null;
    } | null = null;
    if (visit.soapDraft && visit.soapDraft.trim() !== '') {
      const sections = parseSoapSections(visit.soapDraft);
      const byKey = Object.fromEntries(sections.map((s) => [s.key, s.body])) as
        Record<'S' | 'O' | 'A' | 'P', string>;
      previewSoap = {
        subjective: clipForPreview(byKey.S, PREVIEW_SOAP_SECTION_MAX),
        objective:  clipForPreview(byKey.O, PREVIEW_SOAP_SECTION_MAX),
        assessment: clipForPreview(byKey.A, PREVIEW_SOAP_SECTION_MAX),
        plan:       clipForPreview(byKey.P, PREVIEW_SOAP_SECTION_MAX),
      };
    }

    return NextResponse.json(
      {
        visitId: visit.id,
        status,
        progressHint: PROGRESS_HINT[status] ?? status,
        needsReview: visit.needsReview,
        reviewReason: visit.reviewReason,
        audioDurationSec: visit.audioDurationSec,
        deletedAt: visit.deletedAt?.toISOString() ?? null,
        archivedAt: visit.archivedAt?.toISOString() ?? null,
        // Typewriter processing screen consumers
        processingStartedAt: visit.processingStartedAt?.toISOString() ?? null,
        icdCount,
        cptCount,
        preview: {
          soap: previewSoap,
        },
      },
      { status: 200 }
    );
  }
);
